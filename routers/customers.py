from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from database import get_db
import models, schemas
from routers.auth import get_current_admin
from sqlalchemy import func
from utils.auth import get_password_hash

router = APIRouter(prefix="/customers", tags=["customers"])

@router.get("")
def list_customers(
    db: Session = Depends(get_db),
    current_admin: models.User = Depends(get_current_admin)
):
    # Only regulars, not admins
    customers = db.query(models.User).filter(models.User.is_admin == False).all()
    
    result = []
    for c in customers:
        # Calculate stats for each customer
        order_count = db.query(models.Order).filter(models.Order.user_id == c.id).count()
        total_spent = db.query(func.sum(models.Order.total)).filter(models.Order.user_id == c.id).scalar() or 0
        
        result.append({
            "id": c.id,
            "name": c.name,
            "email": c.email,
            "company": c.company,
            "phone": c.phone,
            "address": c.address,
            "city": c.city,
            "state": c.state,
            "zip": c.zip,
            "country": c.country,
            "is_active": c.is_active,
            "total_orders": order_count,
            "total_spent": float(total_spent),
            "created_at": c.created_at,
            "updated_at": c.updated_at
        })
        
    return {"customers": result}

@router.post("", status_code=status.HTTP_201_CREATED)
def create_customer(
    data: schemas.UserCreate,
    db: Session = Depends(get_db),
    current_admin: models.User = Depends(get_current_admin)
):
    # Check if user exists
    existing = db.query(models.User).filter(models.User.email == data.email).first()
    if existing:
        raise HTTPException(status_code=400, detail="User with this email already exists")
    
    customer = models.User(
        email=data.email,
        password_hash=get_password_hash(data.password),
        name=data.name,
        company=data.company,
        phone=data.phone,
        address=data.address,
        city=data.city,
        state=data.state,
        zip=data.zip,
        country=data.country or 'India',
        is_active=data.is_active,
        is_admin=False
    )
    db.add(customer)
    db.commit()
    db.refresh(customer)
    return {"msg": "Customer created", "customer": customer}

@router.get("/{customer_id}")
def get_customer(
    customer_id: int,
    db: Session = Depends(get_db),
    current_admin: models.User = Depends(get_current_admin)
):
    customer = db.query(models.User).filter(models.User.id == customer_id, models.User.is_admin == False).first()
    if not customer:
        raise HTTPException(status_code=404, detail="Customer not found")
        
    order_count = db.query(models.Order).filter(models.Order.user_id == customer.id).count()
    total_spent = db.query(func.sum(models.Order.total)).filter(models.Order.user_id == customer.id).scalar() or 0
    orders = db.query(models.Order).filter(models.Order.user_id == customer.id).all()

    return {
        "customer": {
            "id": customer.id,
            "name": customer.name,
            "email": customer.email,
            "company": customer.company,
            "phone": customer.phone,
            "address": customer.address,
            "city": customer.city,
            "state": customer.state,
            "zip": customer.zip,
            "country": customer.country,
            "is_active": customer.is_active,
            "total_orders": order_count,
            "total_spent": float(total_spent),
            "created_at": customer.created_at,
            "updated_at": customer.updated_at,
            "orders": orders
        }
    }

@router.put("/{customer_id}")
def update_customer(
    customer_id: int,
    data: dict,
    db: Session = Depends(get_db),
    current_admin: models.User = Depends(get_current_admin)
):
    customer = db.query(models.User).filter(models.User.id == customer_id, models.User.is_admin == False).first()
    if not customer:
        raise HTTPException(status_code=404, detail="Customer not found")
    
    for key, value in data.items():
        if hasattr(customer, key):
            if key == "password":
                customer.password_hash = get_password_hash(value)
            else:
                setattr(customer, key, value)
    
    db.commit()
    db.refresh(customer)
    return {"msg": "Customer updated"}

@router.delete("/{customer_id}")
def delete_customer(
    customer_id: int,
    db: Session = Depends(get_db),
    current_admin: models.User = Depends(get_current_admin)
):
    customer = db.query(models.User).filter(models.User.id == customer_id, models.User.is_admin == False).first()
    if not customer:
        raise HTTPException(status_code=404, detail="Customer not found")
    
    # Check for orders
    order_count = db.query(models.Order).filter(models.Order.user_id == customer_id).count()
    if order_count > 0:
        raise HTTPException(status_code=400, detail="Cannot delete customer with existing orders. Consider deactivating instead.")
        
    db.delete(customer)
    db.commit()
    return {"msg": "Customer deleted"}
