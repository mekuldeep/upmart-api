"""
Store Router - Public & Customer-facing API endpoints
All routes here are accessible to frontend users (public or with customer JWT)
"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import func
from database import get_db
import models, schemas
from utils.auth import verify_password, get_password_hash, create_access_token
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
import os
import datetime
from typing import Optional, List
from pydantic import BaseModel, EmailStr

router = APIRouter(prefix="/store", tags=["store"])

customer_oauth2_scheme = OAuth2PasswordBearer(tokenUrl="api/store/login", auto_error=False)

SECRET_KEY = os.getenv("JWT_SECRET_KEY", "dev-secret-key")
ALGORITHM = "HS256"


# ─── Auth helpers ─────────────────────────────────────────────────────────────

def get_current_customer(
    token: str = Depends(customer_oauth2_scheme),
    db: Session = Depends(get_db)
):
    """Returns current user (customer or admin). Raises 401 if token invalid."""
    if not token:
        raise HTTPException(status_code=401, detail="Not authenticated")
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id: str = payload.get("sub")
        if user_id is None:
            raise HTTPException(status_code=401, detail="Invalid token")
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid token")
    user = db.query(models.User).filter(models.User.id == int(user_id)).first()
    if not user or not user.is_active:
        raise HTTPException(status_code=401, detail="User not found or inactive")
    return user


def get_optional_customer(
    token: str = Depends(customer_oauth2_scheme),
    db: Session = Depends(get_db)
):
    """Returns current user or None if not authenticated (for optional auth routes)."""
    if not token:
        return None
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id: str = payload.get("sub")
        if user_id is None:
            return None
    except JWTError:
        return None
    return db.query(models.User).filter(models.User.id == int(user_id)).first()


# ─── Pydantic models ───────────────────────────────────────────────────────────

class RegisterRequest(BaseModel):
    name: str
    email: EmailStr
    password: str
    phone: Optional[str] = None
    company: Optional[str] = None

class LoginRequest(BaseModel):
    email: EmailStr
    password: str

class ProfileUpdateRequest(BaseModel):
    name: Optional[str] = None
    phone: Optional[str] = None
    company: Optional[str] = None
    address: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    zip: Optional[str] = None
    country: Optional[str] = None

class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str

class CouponValidateRequest(BaseModel):
    code: str
    cart_total: float

class StoreOrderItemRequest(BaseModel):
    product_id: int
    quantity: int
    variant_name: Optional[str] = None

class PlaceOrderRequest(BaseModel):
    items: List[StoreOrderItemRequest]
    coupon_code: Optional[str] = None
    notes: Optional[str] = None
    payment_method: str = "cod"
    shipping_address: Optional[str] = None


def validate_coupon_for_total(db: Session, code: str, cart_total: float):
    coupon = db.query(models.Coupon).filter(
        models.Coupon.code == code.upper().strip(),
        models.Coupon.is_active == True
    ).first()

    if not coupon:
        raise HTTPException(status_code=404, detail="Invalid coupon code")

    now = datetime.datetime.utcnow()
    if coupon.valid_from and coupon.valid_from > now:
        raise HTTPException(status_code=400, detail="This coupon is not yet active")
    if coupon.valid_to and coupon.valid_to < now:
        raise HTTPException(status_code=400, detail="This coupon has expired")

    if coupon.min_order_amount and cart_total < float(coupon.min_order_amount):
        raise HTTPException(
            status_code=400,
            detail=f"Minimum order amount of INR {coupon.min_order_amount} required for this coupon"
        )

    if coupon.max_uses and coupon.used_count >= coupon.max_uses:
        raise HTTPException(status_code=400, detail="This coupon has reached its usage limit")

    discount_amount = 0.0
    if coupon.discount_type == 'percentage':
        discount_amount = cart_total * (float(coupon.discount_value) / 100)
        if coupon.max_discount_amount:
            discount_amount = min(discount_amount, float(coupon.max_discount_amount))
    elif coupon.discount_type == 'fixed':
        discount_amount = min(float(coupon.discount_value), cart_total)

    return coupon, round(discount_amount, 2)


# ─── Auth Endpoints ────────────────────────────────────────────────────────────

@router.post("/register", status_code=201)
def register(data: RegisterRequest, db: Session = Depends(get_db)):
    """Register a new customer account."""
    existing = db.query(models.User).filter(models.User.email == data.email).first()
    if existing:
        raise HTTPException(status_code=400, detail="An account with this email already exists")
    
    user = models.User(
        email=data.email,
        password_hash=get_password_hash(data.password),
        name=data.name,
        phone=data.phone,
        company=data.company,
        is_admin=False,
        is_active=True
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    
    access_token = create_access_token(data={"sub": str(user.id)})
    return {
        "access_token": access_token,
        "token_type": "bearer",
        "user": {
            "id": user.id,
            "name": user.name,
            "email": user.email,
            "phone": user.phone,
            "company": user.company,
            "is_admin": user.is_admin,
        }
    }


@router.post("/login")
def login(data: LoginRequest, db: Session = Depends(get_db)):
    """Login a customer (non-admin). Admins cannot use this endpoint."""
    user = db.query(models.User).filter(models.User.email == data.email).first()
    if not user or not verify_password(data.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Invalid email or password")
    if not user.is_active:
        raise HTTPException(status_code=403, detail="Account is deactivated. Please contact support.")
    
    access_token = create_access_token(data={"sub": str(user.id)})
    return {
        "access_token": access_token,
        "token_type": "bearer",
        "user": {
            "id": user.id,
            "name": user.name,
            "email": user.email,
            "phone": user.phone,
            "company": user.company,
            "address": user.address,
            "city": user.city,
            "state": user.state,
            "zip": user.zip,
            "country": user.country,
            "is_admin": user.is_admin,
        }
    }


@router.get("/me")
def get_me(current_user: models.User = Depends(get_current_customer)):
    """Get current logged-in user profile."""
    return {
        "user": {
            "id": current_user.id,
            "name": current_user.name,
            "email": current_user.email,
            "phone": current_user.phone,
            "company": current_user.company,
            "address": current_user.address,
            "city": current_user.city,
            "state": current_user.state,
            "zip": current_user.zip,
            "country": current_user.country,
            "is_admin": current_user.is_admin,
            "created_at": current_user.created_at,
        }
    }


@router.put("/me")
def update_profile(
    data: ProfileUpdateRequest,
    current_user: models.User = Depends(get_current_customer),
    db: Session = Depends(get_db)
):
    """Update the currently logged-in user's profile."""
    update_data = data.dict(exclude_none=True)
    for key, value in update_data.items():
        if hasattr(current_user, key):
            setattr(current_user, key, value)
    db.commit()
    db.refresh(current_user)
    return {
        "msg": "Profile updated",
        "user": {
            "id": current_user.id,
            "name": current_user.name,
            "email": current_user.email,
            "phone": current_user.phone,
            "company": current_user.company,
            "address": current_user.address,
            "city": current_user.city,
            "state": current_user.state,
            "zip": current_user.zip,
            "country": current_user.country,
        }
    }


@router.post("/me/change-password")
def change_password(
    data: ChangePasswordRequest,
    current_user: models.User = Depends(get_current_customer),
    db: Session = Depends(get_db)
):
    """Change the current user's password."""
    if not verify_password(data.current_password, current_user.password_hash):
        raise HTTPException(status_code=400, detail="Current password is incorrect")
    current_user.password_hash = get_password_hash(data.new_password)
    db.commit()
    return {"msg": "Password updated successfully"}


# ─── Public Catalog Endpoints ──────────────────────────────────────────────────

@router.get("/categories")
def list_categories_public(db: Session = Depends(get_db)):
    """List all categories (public, no auth required)."""
    categories = db.query(models.Category).order_by(models.Category.name).all()
    result = []
    for c in categories:
        product_count = db.query(models.Product).filter(
            models.Product.category_id == c.id,
            models.Product.status == 'active'
        ).count()
        result.append({
            "id": c.id,
            "name": c.name,
            "slug": c.slug,
            "description": c.description,
            "parent_id": c.parent_id,
            "product_count": product_count,
        })
    return {"categories": result}


@router.get("/products")
def list_products_public(
    page: int = 1,
    per_page: int = 20,
    search: str = "",
    category_id: Optional[int] = None,
    category_slug: Optional[str] = None,
    sort: str = "newest",  # newest, price_asc, price_desc, name
    min_price: Optional[float] = None,
    max_price: Optional[float] = None,
    db: Session = Depends(get_db)
):
    """List active products (public, no auth required)."""
    query = db.query(models.Product).filter(models.Product.status == 'active')
    
    # Category filter by id or slug
    if category_id:
        query = query.filter(models.Product.category_id == category_id)
    elif category_slug:
        cat = db.query(models.Category).filter(models.Category.slug == category_slug).first()
        if cat:
            # Include subcategory products too
            sub_ids = [s.id for s in cat.children] + [cat.id]
            query = query.filter(models.Product.category_id.in_(sub_ids))
    
    # Search
    if search:
        query = query.filter(
            models.Product.name.ilike(f'%{search}%') |
            models.Product.description.ilike(f'%{search}%') |
            models.Product.sku.ilike(f'%{search}%')
        )
    
    # Price range
    if min_price is not None:
        query = query.filter(models.Product.price >= min_price)
    if max_price is not None:
        query = query.filter(models.Product.price <= max_price)
    
    # Sorting
    if sort == "price_asc":
        query = query.order_by(models.Product.price.asc())
    elif sort == "price_desc":
        query = query.order_by(models.Product.price.desc())
    elif sort == "name":
        query = query.order_by(models.Product.name.asc())
    else:  # newest
        query = query.order_by(models.Product.created_at.desc())
    
    total = query.count()
    products = query.offset((page - 1) * per_page).limit(per_page).all()
    
    products_data = []
    for p in products:
        # Build image data
        variants_data = []
        for v in p.variants:
            v_images = [{"id": i.id, "url": f"/uploads/products/{i.filename}", "is_primary": i.is_primary} for i in v.images]
            variants_data.append({
                "id": v.id, 
                "name": v.name, 
                "price": float(v.price) if v.price else float(p.price),
                "stock": v.stock,
                "images": v_images
            })

        product_images = [{"id": i.id, "url": f"/uploads/products/{i.filename}", "is_primary": i.is_primary} for i in p.images if not i.variant_id]
        
        # Primary image logic (Global across product and variants)
        # 1. Product-level image marked as primary
        # 2. Variant-level image marked as primary
        # 3. Fallback to first product-level image
        # 4. Fallback to first image of first variant
        primary_image = next((img for img in product_images if img['is_primary']), None)
        if not primary_image:
            for v in variants_data:
                primary_image = next((img for img in v['images'] if img['is_primary']), None)
                if primary_image: break
        
        if not primary_image:
            if product_images:
                primary_image = product_images[0]
            elif variants_data:
                for v in variants_data:
                    if v['images']:
                        primary_image = v['images'][0]
                        break
        
        products_data.append({
            "id": p.id,
            "name": p.name,
            "sku": p.sku,
            "description": p.description,
            "price": float(p.price),
            "stock": p.stock,
            "category_id": p.category_id,
            "category_name": p.category.name if p.category else None,
            "category_slug": p.category.slug if p.category else None,
            "min_order_qty": p.min_order_qty,
            "is_group_order_enabled": p.is_group_order_enabled,
            "group_size": p.group_size,
            "sizes": p.sizes or [],
            "variants": variants_data,
            "images": product_images,
            "primary_image": primary_image,
            "in_stock": p.stock > 0 or (any(v.stock > 0 for v in p.variants) if p.variants else False),
            "created_at": p.created_at,
        })
    
    return {
        "products": products_data,
        "total": total,
        "page": page,
        "per_page": per_page,
        "pages": (total + per_page - 1) // per_page
    }


@router.get("/products/{product_id}")
def get_product_public(product_id: int, db: Session = Depends(get_db)):
    """Get a single product by ID (public)."""
    product = db.query(models.Product).filter(
        models.Product.id == product_id,
        models.Product.status == 'active'
    ).first()
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    
    variants_data = []
    for v in product.variants:
        v_images = [{"id": i.id, "url": f"/uploads/products/{i.filename}", "is_primary": i.is_primary} for i in v.images]
        variants_data.append({
            "id": v.id, 
            "name": v.name, 
            "price": float(v.price) if v.price else float(product.price),
            "stock": v.stock,
            "images": v_images
        })

    product_images = [{"id": i.id, "url": f"/uploads/products/{i.filename}", "is_primary": i.is_primary} for i in product.images if not i.variant_id]
    
    # Primary image logic (re-using same consolidated logic)
    primary_image = next((img for img in product_images if img['is_primary']), None)
    if not primary_image:
        for v in variants_data:
            primary_image = next((img for img in v['images'] if img['is_primary']), None)
            if primary_image: break
    
    if not primary_image:
        if product_images:
            primary_image = product_images[0]
        elif variants_data:
            for v in variants_data:
                if v['images']:
                    primary_image = v['images'][0]
                    break
    
    # Related products (same category)
    related = []
    if product.category_id:
        related_products = db.query(models.Product).filter(
            models.Product.category_id == product.category_id,
            models.Product.id != product.id,
            models.Product.status == 'active'
        ).limit(4).all()
        for rp in related_products:
            rp_images = [{"url": f"/uploads/products/{i.filename}", "is_primary": i.is_primary} for i in rp.images if not i.variant_id]
            if not rp_images and rp.variants:
                for rv in rp.variants:
                    for ri in rv.images:
                        rp_images.append({"url": f"/uploads/products/{ri.filename}", "is_primary": ri.is_primary})
                        break
                    break
            rp_primary = next((i for i in rp_images if i['is_primary']), rp_images[0] if rp_images else None)
            related.append({
                "id": rp.id,
                "name": rp.name,
                "price": float(rp.price),
                "primary_image": rp_primary,
                "stock": rp.stock,
                "in_stock": rp.stock > 0 or (any(v.stock > 0 for v in rp.variants) if rp.variants else False),
            })
    
    return {
        "product": {
            "id": product.id,
            "name": product.name,
            "sku": product.sku,
            "description": product.description,
            "price": float(product.price),
            "stock": product.stock,
            "in_stock": product.stock > 0,
            "category_id": product.category_id,
            "category_name": product.category.name if product.category else None,
            "category_slug": product.category.slug if product.category else None,
            "min_order_qty": product.min_order_qty,
            "is_group_order_enabled": product.is_group_order_enabled,
            "group_size": product.group_size,
            "sizes": product.sizes or [],
            "variants": variants_data,
            "images": product_images,
            "primary_image": primary_image,
            "created_at": product.created_at,
        },
        "related": related
    }


# ─── Coupon Validation ─────────────────────────────────────────────────────────

@router.post("/validate-coupon")
def validate_coupon(
    data: CouponValidateRequest,
    db: Session = Depends(get_db),
    current_user: Optional[models.User] = Depends(get_optional_customer)
):
    """Validate and apply a coupon code to the cart."""
    if data.cart_total <= 0:
        raise HTTPException(status_code=400, detail="Cart total must be greater than 0")

    coupon, discount_amount = validate_coupon_for_total(db, data.code, data.cart_total)
    
    return {
        "valid": True,
        "coupon": {
            "id": coupon.id,
            "code": coupon.code,
            "discount_type": coupon.discount_type,
            "discount_value": float(coupon.discount_value),
            "description": coupon.description,
        },
        "discount_amount": discount_amount,
        "final_total": round(data.cart_total - discount_amount, 2)
    }


# ─── Orders ────────────────────────────────────────────────────────────────────

@router.post("/orders", status_code=201)
def place_order(
    data: PlaceOrderRequest,
    current_user: models.User = Depends(get_current_customer),
    db: Session = Depends(get_db)
):
    """Place an order from the storefront."""
    if not data.items:
        raise HTTPException(status_code=400, detail="Order must have at least one item")
    
    processed_items = []
    subtotal = 0.0
    
    for item_data in data.items:
        product = db.query(models.Product).filter(
            models.Product.id == item_data.product_id,
            models.Product.status == 'active'
        ).first()
        if not product:
            raise HTTPException(status_code=404, detail=f"Product ID {item_data.product_id} not found")
        
        if item_data.quantity < product.min_order_qty:
            raise HTTPException(
                status_code=400,
                detail=f"Minimum order quantity for '{product.name}' is {product.min_order_qty}"
            )
        
        if product.is_group_order_enabled and product.group_size:
            if item_data.quantity % product.group_size != 0:
                raise HTTPException(
                    status_code=400,
                    detail=f"Quantity for '{product.name}' must be in multiples of {product.group_size}"
                )
        
        # Check variant if provided
        target_price = float(product.price)
        target_stock = product.stock
        variant_id = None

        if item_data.variant_name:
            variant = db.query(models.ProductVariant).filter(
                models.ProductVariant.product_id == product.id,
                models.ProductVariant.name == item_data.variant_name
            ).first()
            if variant:
                if variant.price:
                    target_price = float(variant.price)
                target_stock = variant.stock
                variant_id = variant.id
            else:
                raise HTTPException(status_code=400, detail=f"Variant '{item_data.variant_name}' not found for '{product.name}'")

        if target_stock < item_data.quantity:
            raise HTTPException(
                status_code=400,
                detail=f"Insufficient stock for '{product.name}'{f' ({item_data.variant_name})' if item_data.variant_name else ''}. Available: {target_stock}"
            )
        
        line_total = target_price * item_data.quantity
        processed_items.append({
            'product': product,
            'variant_id': variant_id,
            'quantity': item_data.quantity,
            'unit_price': target_price,
            'line_total': line_total,
        })
        subtotal += line_total
    
    # Apply coupon if provided
    discount_amount = 0.0
    coupon_obj = None
    if data.coupon_code:
        coupon_obj, discount_amount = validate_coupon_for_total(db, data.coupon_code, subtotal)
    
    total = round(subtotal - discount_amount, 2)
    
    # Create order
    order_number = f"UPM-{datetime.datetime.now().strftime('%Y%m%d%H%M%S')}-{current_user.id}"
    order = models.Order(
        order_number=order_number,
        user_id=current_user.id,
        total=total,
        status='pending',
        notes=data.notes or (f"Payment: {data.payment_method}" + (f" | Shipping: {data.shipping_address}" if data.shipping_address else ""))
    )
    db.add(order)
    db.commit()
    db.refresh(order)
    
    # Create order items & reduce stock
    for pi in processed_items:
        order_item = models.OrderItem(
            order_id=order.id,
            product_id=pi['product'].id,
            quantity=pi['quantity'],
            unit_price=pi['unit_price']
        )
        db.add(order_item)
        # Reduce stock
        if pi['variant_id']:
            variant = db.query(models.ProductVariant).filter(models.ProductVariant.id == pi['variant_id']).first()
            if variant:
                variant.stock -= pi['quantity']
        else:
            pi['product'].stock -= pi['quantity']
    
    # Create payment record
    payment = models.Payment(
        order_id=order.id,
        amount=total,
        payment_method=data.payment_method,
        status='pending' if data.payment_method == 'cod' else 'completed'
    )
    db.add(payment)
    
    # Initial order history
    history = models.OrderHistory(
        order_id=order.id,
        status='pending',
        notes="Order placed by customer" + (f" | Coupon: {data.coupon_code}" if data.coupon_code else "")
    )
    db.add(history)
    
    # Increment coupon usage
    if coupon_obj:
        coupon_obj.used_count = (coupon_obj.used_count or 0) + 1
    
    db.commit()
    
    return {
        "msg": "Order placed successfully",
        "order": {
            "id": order.id,
            "order_number": order.order_number,
            "status": order.status,
            "subtotal": subtotal,
            "discount": discount_amount,
            "total": total,
            "payment_method": data.payment_method,
            "created_at": order.created_at,
        }
    }


@router.get("/orders")
def my_orders(
    page: int = 1,
    current_user: models.User = Depends(get_current_customer),
    db: Session = Depends(get_db)
):
    """Get current user's orders."""
    query = db.query(models.Order).filter(models.Order.user_id == current_user.id)
    total = query.count()
    orders = query.order_by(models.Order.created_at.desc()).offset((page - 1) * 10).limit(10).all()
    
    result = []
    for o in orders:
        result.append({
            "id": o.id,
            "order_number": o.order_number,
            "status": o.status,
            "total": float(o.total),
            "item_count": len(o.items),
            "created_at": o.created_at,
            "items": [{
                "id": i.id,
                "product_id": i.product_id,
                "product_name": i.product.name if i.product else None,
                "quantity": i.quantity,
                "unit_price": float(i.unit_price),
                "line_total": float(i.unit_price * i.quantity),
            } for i in o.items]
        })
    
    return {
        "orders": result,
        "total": total,
        "page": page,
        "pages": (total + 9) // 10
    }


@router.get("/orders/{order_id}")
def get_my_order(
    order_id: int,
    current_user: models.User = Depends(get_current_customer),
    db: Session = Depends(get_db)
):
    """Get a specific order belonging to the current user."""
    order = db.query(models.Order).filter(
        models.Order.id == order_id,
        models.Order.user_id == current_user.id
    ).first()
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    
    return {
        "order": {
            "id": order.id,
            "order_number": order.order_number,
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
                "line_total": float(i.unit_price * i.quantity),
            } for i in order.items],
            "payments": [{
                "id": p.id,
                "amount": float(p.amount),
                "payment_method": p.payment_method,
                "status": p.status,
                "created_at": p.created_at,
            } for p in order.payments],
            "history": sorted([{
                "id": h.id,
                "status": h.status,
                "notes": h.notes,
                "created_at": h.created_at,
            } for h in order.histories], key=lambda x: x['created_at'])
        }
    }
