"""
Coupons Admin Router
"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.exc import IntegrityError
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


class CouponUpdate(BaseModel):
    code: Optional[str] = None
    description: Optional[str] = None
    discount_type: Optional[str] = None
    discount_value: Optional[float] = None
    min_order_amount: Optional[float] = None
    max_discount_amount: Optional[float] = None
    max_uses: Optional[int] = None
    is_active: Optional[bool] = None
    valid_from: Optional[datetime] = None
    valid_to: Optional[datetime] = None


def validate_coupon_fields(data: dict):
    discount_type = data.get("discount_type")
    discount_value = data.get("discount_value")
    min_order_amount = data.get("min_order_amount")
    max_discount_amount = data.get("max_discount_amount")
    max_uses = data.get("max_uses")
    valid_from = data.get("valid_from")
    valid_to = data.get("valid_to")

    if discount_type is not None and discount_type not in ["percentage", "fixed"]:
        raise HTTPException(status_code=400, detail="discount_type must be 'percentage' or 'fixed'")
    if discount_value is not None and discount_value <= 0:
        raise HTTPException(status_code=400, detail="Discount must be greater than 0")
    if discount_type == "percentage" and discount_value is not None and discount_value > 100:
        raise HTTPException(status_code=400, detail="Percentage discount cannot be more than 100")
    if min_order_amount is not None and min_order_amount < 0:
        raise HTTPException(status_code=400, detail="Minimum order amount cannot be negative")
    if max_discount_amount is not None and max_discount_amount <= 0:
        raise HTTPException(status_code=400, detail="Maximum discount amount must be greater than 0")
    if max_uses is not None and max_uses < 1:
        raise HTTPException(status_code=400, detail="Usage limit must be at least 1")
    if valid_from and valid_to and valid_to < valid_from:
        raise HTTPException(status_code=400, detail="Coupon expiry must be after start date")


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
    code = data.code.upper().strip()
    if not code:
        raise HTTPException(status_code=400, detail="Coupon code is required")

    validate_coupon_fields(data.dict())

    existing = db.query(models.Coupon).filter(models.Coupon.code == code).first()
    if existing:
        raise HTTPException(status_code=400, detail="Coupon code already exists")

    coupon = models.Coupon(
        code=code,
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
    try:
        db.add(coupon)
        db.commit()
        db.refresh(coupon)
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=400, detail="Coupon could not be created")
    return {"msg": "Coupon created", "coupon": {"id": coupon.id, "code": coupon.code}}


@router.put("/{coupon_id}")
def update_coupon(coupon_id: int, data: CouponUpdate, db: Session = Depends(get_db), current_admin: models.User = Depends(get_current_admin)):
    coupon = db.query(models.Coupon).filter(models.Coupon.id == coupon_id).first()
    if not coupon:
        raise HTTPException(status_code=404, detail="Coupon not found")

    payload = data.dict(exclude_unset=True)
    if "code" in payload and payload["code"] is not None:
        payload["code"] = payload["code"].upper().strip()
        if not payload["code"]:
            raise HTTPException(status_code=400, detail="Coupon code is required")
        existing = db.query(models.Coupon).filter(
            models.Coupon.code == payload["code"],
            models.Coupon.id != coupon_id
        ).first()
        if existing:
            raise HTTPException(status_code=400, detail="Coupon code already exists")

    validate_coupon_fields(payload)

    for key, value in payload.items():
        if hasattr(coupon, key) and key not in ['id', 'used_count', 'created_at']:
            setattr(coupon, key, value)

    try:
        db.commit()
        db.refresh(coupon)
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=400, detail="Coupon could not be updated")
    return {"msg": "Coupon updated"}


@router.delete("/{coupon_id}")
def delete_coupon(coupon_id: int, db: Session = Depends(get_db), current_admin: models.User = Depends(get_current_admin)):
    coupon = db.query(models.Coupon).filter(models.Coupon.id == coupon_id).first()
    if not coupon:
        raise HTTPException(status_code=404, detail="Coupon not found")
    try:
        db.delete(coupon)
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=400, detail="Coupon could not be deleted")
    return {"msg": "Coupon deleted"}
