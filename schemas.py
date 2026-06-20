from pydantic import BaseModel, EmailStr, Field
from typing import List, Optional
from datetime import datetime
from decimal import Decimal

# Base schemas
class CategoryBase(BaseModel):
    name: str
    slug: Optional[str] = None
    description: Optional[str] = None
    parent_id: Optional[int] = None

class CategoryCreate(CategoryBase):
    pass

class Category(CategoryBase):
    id: int
    created_at: datetime
    product_count: Optional[int] = 0

    class Config:
        from_attributes = True

# Product Images
class ProductImageBase(BaseModel):
    filename: str
    is_primary: bool = False

class ProductVariantBase(BaseModel):
    name: str
    price: Optional[Decimal] = Field(default=None, gt=0)
    stock: int = 0

class ProductVariantCreate(ProductVariantBase):
    product_id: int

class ProductVariant(ProductVariantBase):
    id: int
    product_id: int
    images: List['ProductImage'] = []

    class Config:
        from_attributes = True

class ProductImage(ProductImageBase):
    id: int
    product_id: Optional[int] = None
    variant_id: Optional[int] = None
    url: Optional[str] = None

    class Config:
        from_attributes = True

# Re-update ProductVariant to avoid circular dependency issues if any
ProductVariant.model_rebuild()

# Products
class ProductBase(BaseModel):
    name: str
    sku: str
    description: Optional[str] = None
    price: Optional[Decimal] = Field(default=None, gt=0)
    stock: Optional[int] = 0
    category_id: Optional[int] = None
    status: str = 'active'
    min_order_qty: int = 1
    is_group_order_enabled: bool = False
    group_size: Optional[int] = None
    sizes: Optional[List[str]] = []


class ProductCreate(ProductBase):
    variants: Optional[List[ProductVariantBase]] = []

class ProductUpdate(BaseModel):
    name: Optional[str] = None
    sku: Optional[str] = None
    description: Optional[str] = None
    price: Optional[Decimal] = Field(default=None, gt=0)
    stock: Optional[int] = None
    category_id: Optional[int] = None
    status: Optional[str] = None
    min_order_qty: Optional[int] = None
    is_group_order_enabled: Optional[bool] = None
    group_size: Optional[int] = None
    sizes: Optional[List[str]] = None

class Product(ProductBase):
    id: int
    created_at: datetime
    updated_at: datetime
    category_name: Optional[str] = None
    variants: List[ProductVariant] = []
    images: List[ProductImage] = []
    primary_image: Optional[ProductImage] = None

    class Config:
        from_attributes = True

# Users (replacing Customer and Admin)
class UserBase(BaseModel):
    name: str
    email: EmailStr
    company: Optional[str] = None
    phone: Optional[str] = None
    address: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    zip: Optional[str] = None
    country: Optional[str] = 'India'
    is_active: bool = True
    is_admin: bool = False

class UserCreate(UserBase):
    password: str

class User(UserBase):
    id: int
    created_at: datetime
    updated_at: datetime
    total_orders: Optional[int] = 0
    total_spent: Optional[float] = 0

    class Config:
        from_attributes = True

# Order Items
class OrderItemBase(BaseModel):
    product_id: int
    quantity: int
    unit_price: Decimal

class OrderItem(OrderItemBase):
    id: int
    product_name: Optional[str] = None
    product_sku: Optional[str] = None
    line_total: Optional[float] = None

    class Config:
        from_attributes = True

# Payment
class PaymentBase(BaseModel):
    amount: Decimal
    payment_method: str
    transaction_id: Optional[str] = None
    status: str = 'completed'

class PaymentCreate(PaymentBase):
    order_id: int

class Payment(PaymentBase):
    id: int
    created_at: datetime

    class Config:
        from_attributes = True

# Order History
class OrderHistoryBase(BaseModel):
    status: str
    notes: Optional[str] = None

class OrderHistory(OrderHistoryBase):
    id: int
    created_at: datetime

    class Config:
        from_attributes = True

# Orders
class OrderBase(BaseModel):
    status: str = 'pending'
    notes: Optional[str] = None

class OrderCreate(OrderBase):
    user_id: int
    items: List[OrderItemBase]

class Order(OrderBase):
    id: int
    order_number: str
    user_id: int
    customer_name: Optional[str] = None
    total: Decimal
    created_at: datetime
    updated_at: datetime
    items: List[OrderItem] = []
    histories: List[OrderHistory] = []
    payments: List[Payment] = []

    class Config:
        from_attributes = True

# Auth
class Token(BaseModel):
    access_token: str
    token_type: str

class TokenData(BaseModel):
    email: Optional[str] = None

class LoginRequest(BaseModel):
    email: EmailStr
    password: str

class AdminInfo(BaseModel):
    id: int
    email: str
    name: Optional[str] = None
    is_admin: bool

    class Config:
        from_attributes = True
