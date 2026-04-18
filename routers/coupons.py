"""
Coupons Admin Router
"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from database import get_db
import models
from routers.auth import get_current_admin
from typing import Optional
from pydantic import BaseModel
from datetime import datetime

router = APIRouter(prefix="/coupons", tags=["coupons"])


class CouponCreate(BaseModel):
    code: str
    description: Optional[str] = None
    discount_type: str  # 'percentage' or 'fixed'
    discount_value: float
    min_order_amount: Optional[float] = None
    max_discount_amount: Optional[float] = None
    max_uses: Optional[int] = None
    is_active: bool = True
    valid_from: Optional[datetime] = None
    valid_to: Optional[datetime] = None


@router.get("")
def list_coupons(db: Session = Depends(get_db), current_admin: models.User = Depends(get_current_admin)):
    coupons = db.query(models.Coupon).order_by(models.Coupon.created_at.desc()).all()
    return {"coupons": [{
        "id": c.id,
        "code": c.code,
        "description": c.description,
        "discount_type": c.discount_type,
        "discount_value": float(c.discount_value),
        "min_order_amount": float(c.min_order_amount) if c.min_order_amount else None,
        "max_discount_amount": float(c.max_discount_amount) if c.max_discount_amount else None,
        "max_uses": c.max_uses,
        "used_count": c.used_count,
        "is_active": c.is_active,
        "valid_from": c.valid_from,
        "valid_to": c.valid_to,
        "created_at": c.created_at,
    } for c in coupons]}


@router.post("", status_code=201)
def create_coupon(data: CouponCreate, db: Session = Depends(get_db), current_admin: models.User = Depends(get_current_admin)):
    existing = db.query(models.Coupon).filter(models.Coupon.code == data.code.upper().strip()).first()
    if existing:
        raise HTTPException(status_code=400, detail="Coupon code already exists")
    
    if data.discount_type not in ['percentage', 'fixed']:
        raise HTTPException(status_code=400, detail="discount_type must be 'percentage' or 'fixed'")
    
    coupon = models.Coupon(
        code=data.code.upper().strip(),
        description=data.description,
        discount_type=data.discount_type,
        discount_value=data.discount_value,
        min_order_amount=data.min_order_amount,
        max_discount_amount=data.max_discount_amount,
        max_uses=data.max_uses,
        is_active=data.is_active,
        valid_from=data.valid_from,
        valid_to=data.valid_to,
    )
    db.add(coupon)
    db.commit()
    db.refresh(coupon)
    return {"msg": "Coupon created", "coupon": {"id": coupon.id, "code": coupon.code}}


@router.put("/{coupon_id}")
def update_coupon(coupon_id: int, data: dict, db: Session = Depends(get_db), current_admin: models.User = Depends(get_current_admin)):
    coupon = db.query(models.Coupon).filter(models.Coupon.id == coupon_id).first()
    if not coupon:
        raise HTTPException(status_code=404, detail="Coupon not found")
    
    for key, value in data.items():
        if hasattr(coupon, key) and key not in ['id', 'used_count', 'created_at']:
            if key == 'code' and value:
                value = value.upper().strip()
            setattr(coupon, key, value)
    
    db.commit()
    db.refresh(coupon)
    return {"msg": "Coupon updated"}


@router.delete("/{coupon_id}")
def delete_coupon(coupon_id: int, db: Session = Depends(get_db), current_admin: models.User = Depends(get_current_admin)):
    coupon = db.query(models.Coupon).filter(models.Coupon.id == coupon_id).first()
    if not coupon:
        raise HTTPException(status_code=404, detail="Coupon not found")
    db.delete(coupon)
    db.commit()
    return {"msg": "Coupon deleted"}
