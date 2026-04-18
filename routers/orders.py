from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from database import get_db
import models, schemas
from routers.auth import get_current_admin
from typing import List, Optional
import datetime

router = APIRouter(prefix="/orders", tags=["orders"])

def paginate_query(query, page, per_page=20):
    total = query.count()
    items = query.offset((page - 1) * per_page).limit(per_page).all()
    return {
        'items': items,
        'total': total,
        'page': page,
        'per_page': per_page,
        'pages': (total + per_page - 1) // per_page
    }

def validate_quantity(quantity, product):
    if quantity < 1:
        return False, "Quantity must be at least 1"
    if quantity < product.min_order_qty:
        return False, f"Minimum order quantity for this product is {product.min_order_qty} units"
    if product.is_group_order_enabled and product.group_size:
        if quantity % product.group_size != 0:
            return False, f"Quantity must be in multiples of {product.group_size}"
    return True, None

@router.get("")
def list_orders(
    page: int = 1,
    status: Optional[str] = None,
    search: str = "",
    db: Session = Depends(get_db),
    current_admin: models.User = Depends(get_current_admin)
):
    query = db.query(models.Order)
    
    if status:
        query = query.filter(models.Order.status == status)
    
    if search:
        query = query.join(models.User).filter(
            models.User.name.ilike(f'%{search}%') | models.Order.order_number.ilike(f'%{search}%')
        )
    
    paginated = paginate_query(query.order_by(models.Order.created_at.desc()), page)
    
    return {
        "orders": [{
            "id": o.id,
            "order_number": o.order_number,
            "user_id": o.user_id,
            "customer_name": o.customer.name if o.customer else None,
            "status": o.status,
            "total": float(o.total),
            "created_at": o.created_at,
            "updated_at": o.updated_at,
            "item_count": len(o.items)
        } for o in paginated['items']],
        "total": paginated['total'],
        "page": paginated['page'],
        "pages": paginated['pages']
    }

@router.get("/{order_id}")
def get_order(
    order_id: int,
    db: Session = Depends(get_db),
    current_admin: models.User = Depends(get_current_admin)
):
    order = db.query(models.Order).filter(models.Order.id == order_id).first()
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    
    return {
        "order": {
            "id": order.id,
            "order_number": order.order_number,
            "user_id": order.user_id,
            "customer_name": order.customer.name if order.customer else None,
            "customer_email": order.customer.email if order.customer else None,
            "status": order.status,
            "total": float(order.total),
            "notes": order.notes,
            "created_at": order.created_at,
            "updated_at": order.updated_at,
            "items": [{
                "id": i.id,
                "product_id": i.product_id,
                "product_name": i.product.name if i.product else None,
                "quantity": i.quantity,
                "unit_price": float(i.unit_price),
                "line_total": float(i.unit_price * i.quantity)
            } for i in order.items],
            "payments": [{
                "id": p.id,
                "amount": float(p.amount),
                "payment_method": p.payment_method,
                "transaction_id": p.transaction_id,
                "status": p.status,
                "created_at": p.created_at
            } for p in order.payments],
            "histories": sorted([{
                "id": h.id,
                "status": h.status,
                "notes": h.notes,
                "created_at": h.created_at
            } for h in order.histories], key=lambda x: x['created_at'], reverse=True)
        }
    }

@router.patch("/{order_id}/status")
def update_order_status(
    order_id: int,
    data: dict,
    db: Session = Depends(get_db),
    current_admin: models.User = Depends(get_current_admin)
):
    order = db.query(models.Order).filter(models.Order.id == order_id).first()
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
        
    new_status = data.get('status')
    allowed_statuses = ['pending', 'processing', 'shipped', 'delivered', 'cancelled']
    
    if new_status not in allowed_statuses:
        raise HTTPException(status_code=400, detail=f"Invalid status. Allowed: {', '.join(allowed_statuses)}")
    
    old_status = order.status
    order.status = new_status
    
    # Create history entry
    history = models.OrderHistory(
        order_id=order.id,
        status=new_status,
        notes=data.get('notes') or f"Status changed from {old_status} to {new_status}"
    )
    db.add(history)
    db.commit()
    
    return {"msg": "Order status updated", "status": order.status}

@router.post("/{order_id}/payments")
def create_payment(
    order_id: int,
    data: schemas.PaymentBase,
    db: Session = Depends(get_db),
    current_admin: models.User = Depends(get_current_admin)
):
    order = db.query(models.Order).filter(models.Order.id == order_id).first()
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    
    payment = models.Payment(
        order_id=order_id,
        amount=data.amount,
        payment_method=data.payment_method,
        transaction_id=data.transaction_id,
        status=data.status
    )
    db.add(payment)
    db.commit()
    db.refresh(payment)
    return {"msg": "Payment recorded", "payment": {
        "id": payment.id,
        "amount": float(payment.amount),
        "payment_method": payment.payment_method,
        "transaction_id": payment.transaction_id,
        "status": payment.status,
        "created_at": payment.created_at
    }}

@router.post("", status_code=status.HTTP_201_CREATED)
def create_order(
    data: schemas.OrderCreate,
    db: Session = Depends(get_db),
    current_admin: models.User = Depends(get_current_admin)
):
    customer = db.query(models.User).filter(models.User.id == data.user_id).first()
    if not customer:
        raise HTTPException(status_code=404, detail="Customer not found")
    
    processed_items = []
    total = 0

    for item_data in data.items:
        product = db.query(models.Product).filter(models.Product.id == item_data.product_id).first()
        if not product:
            raise HTTPException(status_code=404, detail=f"Product {item_data.product_id} not found")
        
        is_valid, error = validate_quantity(item_data.quantity, product)
        if not is_valid:
            raise HTTPException(status_code=400, detail=f"Product '{product.name}': {error}")
            
        processed_items.append({
            'product_id': product.id,
            'quantity': item_data.quantity,
            'unit_price': product.price
        })
        total += product.price * item_data.quantity

    order_number = f"ORD-{datetime.datetime.now().strftime('%Y%m%d%H%M%S')}"
    order = models.Order(
        order_number=order_number,
        user_id=customer.id,
        total=total,
        status=data.status,
        notes=data.notes
    )
    
    db.add(order)
    db.commit()
    db.refresh(order)

    for pi in processed_items:
        order_item = models.OrderItem(
            order_id=order.id,
            product_id=pi['product_id'],
            quantity=pi['quantity'],
            unit_price=pi['unit_price']
        )
        db.add(order_item)
    
    db.commit()
    db.refresh(order)
    
    # Create initial history entry
    history = models.OrderHistory(
        order_id=order.id,
        status=order.status,
        notes="Order created"
    )
    db.add(history)
    db.commit()
    
    return {"msg": "Order created", "order": order}
