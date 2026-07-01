from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, Form
from sqlalchemy.orm import Session, aliased
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from database import get_db
import models, schemas
from routers.auth import get_current_admin
from typing import List, Optional, Any
from decimal import Decimal
import os
import uuid
import shutil
import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/products", tags=["products"])

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
UPLOAD_DIR = os.path.join(BASE_DIR, "uploads", "products")
os.makedirs(UPLOAD_DIR, exist_ok=True)

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

def allowed_image_file(filename):
    if not filename: return False
    ALLOWED_EXTENSIONS = {'jpg', 'jpeg', 'png', 'webp', 'gif', 'jfif', 'pjpeg', 'pjp', 'svg'}
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def sync_product_totals_from_variants(product: models.Product):
    variants = list(product.variants or [])
    if not variants:
        product.stock = 0
        return

    product.stock = sum(v.stock or 0 for v in variants)
    first_priced_variant = next((v for v in variants if v.price is not None), None)
    if first_priced_variant:
        product.price = first_priced_variant.price

def category_display_name(category: Optional[models.Category]) -> Optional[str]:
    if not category:
        return None
    if category.parent:
        return f"{category.parent.name} / {category.name}"
    return category.name

@router.get("")
def list_products(
    page: int = 1,
    search: str = "",
    category_id: Optional[int] = None,
    status: Optional[str] = None,
    db: Session = Depends(get_db),
    current_admin: models.User = Depends(get_current_admin)
):
    ParentCategory = aliased(models.Category)
    query = (
        db.query(models.Product)
        .join(models.Product.category, isouter=True)
        .join(ParentCategory, models.Category.parent_id == ParentCategory.id, isouter=True)
    )

    if search:
        query = query.filter(
            models.Product.name.ilike(f'%{search}%') | 
            models.Product.sku.ilike(f'%{search}%') |
            models.Category.name.ilike(f'%{search}%') |
            ParentCategory.name.ilike(f'%{search}%')
        )
    
    if category_id:
        category = db.query(models.Category).filter(models.Category.id == category_id).first()
        category_ids = [category_id]
        if category and category.parent_id is None:
            category_ids.extend(child.id for child in category.children)
        query = query.filter(models.Product.category_id.in_(category_ids))
    
    if status:
        query = query.filter(models.Product.status == status)
    else:
        query = query.filter(models.Product.status != 'archived')

    paginated = paginate_query(query.order_by(models.Product.created_at.desc()), page)
    
    products_data = []
    for p in paginated['items']:
        # Build variants data with images
        variants_data = []
        for v in p.variants:
            v_images = [{"id": img.id, "filename": img.filename, "is_primary": img.is_primary, "url": f"/uploads/products/{img.filename}", "variant_id": img.variant_id} for img in v.images]
            variants_data.append({
                "id": v.id,
                "name": v.name,
                "price": float(v.price) if v.price else None,
                "stock": v.stock,
                "images": v_images
            })

        # Product-level images (variant_id is None)
        product_images = [{"id": img.id, "filename": img.filename, "is_primary": img.is_primary, "url": f"/uploads/products/{img.filename}", "variant_id": img.variant_id} for img in p.images if not img.variant_id]
        
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
            "category_path": category_display_name(p.category),
            "status": p.status,
            "min_order_qty": p.min_order_qty,
            "is_group_order_enabled": p.is_group_order_enabled,
            "group_size": p.group_size,
            "sizes": p.sizes or [],
            "created_at": p.created_at,
            "updated_at": p.updated_at,
            "variants": variants_data,
            "images": product_images,
            "primary_image": primary_image
        })

    return {
        "products": products_data,
        "total": paginated['total'],
        "page": paginated['page'],
        "pages": paginated['pages']
    }

@router.post("", status_code=status.HTTP_201_CREATED)
def create_product(
    data: schemas.ProductCreate,
    db: Session = Depends(get_db),
    current_admin: models.User = Depends(get_current_admin)
):
    if data.price is None:
        raise HTTPException(status_code=400, detail="Price is required")

    if data.price <= Decimal("0"):
        raise HTTPException(status_code=400, detail="Price must be greater than 0")

    if db.query(models.Product).filter(models.Product.sku == data.sku).first():
        raise HTTPException(status_code=400, detail="Product with this SKU already exists")

    product_data = data.model_dump()
    variants_data = product_data.pop('variants', [])
    
    product = models.Product(**product_data)
    db.add(product)
    created_variants = []
    try:
        db.flush()

        # Create variants if provided
        for v_data in variants_data:
            variant = models.ProductVariant(
                product_id=product.id, 
                name=v_data['name'], 
                price=v_data.get('price'),
                stock=v_data.get('stock', 0)
            )
            db.add(variant)
            created_variants.append(variant)

        if created_variants:
            product.stock = sum(v.stock or 0 for v in created_variants)
            if created_variants[0].price is not None:
                product.price = created_variants[0].price

        db.commit()
        for v in created_variants:
            db.refresh(v)
        db.refresh(product)
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=400, detail="Could not create product")

    return {
        "msg": "Product created", 
        "product": {
            "id": product.id,
            "name": product.name,
            "sku": product.sku,
            "variants": [{"id": v.id, "name": v.name, "price": float(v.price) if v.price else None, "stock": v.stock} for v in created_variants]
        }
    }

@router.get("/{product_id}")
def get_product(
    product_id: int,
    db: Session = Depends(get_db),
    current_admin: models.User = Depends(get_current_admin)
):
    product = db.query(models.Product).filter(models.Product.id == product_id).first()
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    
    variants_data = []
    for v in product.variants:
        v_images = [{"id": img.id, "filename": img.filename, "is_primary": img.is_primary, "url": f"/uploads/products/{img.filename}", "variant_id": img.variant_id} for img in v.images]
        variants_data.append({
            "id": v.id,
            "name": v.name,
            "price": float(v.price) if v.price else None,
            "stock": v.stock,
            "images": v_images
        })

    product_images = [{"id": img.id, "filename": img.filename, "is_primary": img.is_primary, "url": f"/uploads/products/{img.filename}", "variant_id": img.variant_id} for img in product.images if not img.variant_id]
    
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

    return {
        "product": {
            "id": product.id,
            "name": product.name,
            "sku": product.sku,
            "description": product.description,
            "price": float(product.price),
            "stock": product.stock,
            "category_id": product.category_id,
            "category_name": product.category.name if product.category else None,
            "category_path": category_display_name(product.category),
            "status": product.status,
            "min_order_qty": product.min_order_qty,
            "is_group_order_enabled": product.is_group_order_enabled,
            "group_size": product.group_size,
            "sizes": product.sizes or [],
            "created_at": product.created_at,
            "updated_at": product.updated_at,
            "variants": variants_data,
            "images": product_images,
            "primary_image": primary_image
        }
    }

@router.put("/{product_id}")
def update_product(
    product_id: int,
    data: schemas.ProductUpdate,
    db: Session = Depends(get_db),
    current_admin: models.User = Depends(get_current_admin)
):
    product = db.query(models.Product).filter(models.Product.id == product_id).first()
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")

    update_data = data.model_dump(exclude_unset=True)

    if "price" in update_data:
        if update_data["price"] is None:
            raise HTTPException(status_code=400, detail="Price is required")
        if update_data["price"] <= Decimal("0"):
            raise HTTPException(status_code=400, detail="Price must be greater than 0")

    if 'sku' in update_data and update_data['sku'] != product.sku:
        if db.query(models.Product).filter(models.Product.sku == update_data['sku']).first():
            raise HTTPException(status_code=400, detail="Product with this SKU already exists")

    for key, value in update_data.items():
        if hasattr(product, key):
            setattr(product, key, value)

    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=400, detail="Could not update product")
    db.refresh(product)
    return {"msg": "Product updated", "product": product}

@router.patch("/{product_id}/archive")
def archive_product(
    product_id: int,
    db: Session = Depends(get_db),
    current_admin: models.User = Depends(get_current_admin)
):
    product = db.query(models.Product).filter(models.Product.id == product_id).first()
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")

    product.status = 'archived'
    try:
        db.commit()
    except SQLAlchemyError:
        db.rollback()
        logger.exception("Database error while archiving product %s", product_id)
        raise HTTPException(status_code=500, detail="Could not archive product")

    return {"msg": "Product archived", "archived": True}

@router.delete("/{product_id}")
def delete_product(
    product_id: int,
    force: bool = False,
    db: Session = Depends(get_db),
    current_admin: models.User = Depends(get_current_admin)
):
    product = db.query(models.Product).filter(models.Product.id == product_id).first()
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")

    order_ids = [
        order_id for (order_id,) in db.query(models.OrderItem.order_id)
        .filter(models.OrderItem.product_id == product_id)
        .distinct()
        .all()
    ]

    if order_ids and not force:
        raise HTTPException(
            status_code=409,
            detail={
                "message": (
                    f"This product has {len(order_ids)} related order(s). "
                    "Deleting this product will delete the related order(s) as well."
                ),
                "order_count": len(order_ids),
                "requires_confirmation": True,
            },
        )

    image_paths = [
        os.path.join(UPLOAD_DIR, img.filename)
        for img in product.images
        if img.filename
    ]

    try:
        if order_ids:
            related_orders = db.query(models.Order).filter(models.Order.id.in_(order_ids)).all()
            for order in related_orders:
                db.delete(order)
            db.flush()

        db.delete(product)
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=409,
            detail="Cannot delete product because it is still used by existing records",
        )
    except SQLAlchemyError:
        db.rollback()
        logger.exception("Database error while deleting product %s", product_id)
        raise HTTPException(status_code=500, detail="Could not delete product")

    for file_path in image_paths:
        try:
            if os.path.exists(file_path):
                os.remove(file_path)
        except OSError:
            logger.warning("Could not delete product image file %s", file_path, exc_info=True)

    return {
        "msg": "Product and related orders deleted" if order_ids else "Product deleted",
        "deleted_orders": len(order_ids),
    }

@router.post("/{product_id}/images")
def upload_images(
    product_id: int,
    images: List[UploadFile] = File(...),
    variant_id: Any = Form(None),
    db: Session = Depends(get_db),
    current_admin: models.User = Depends(get_current_admin)
):
    print(f"DEBUG: Upload images hit for product {product_id}, variant {variant_id}")
    print(f"DEBUG: Received {len(images)} images")
    
    # Handle stringified null/undefined from FormData
    actual_variant_id = None
    if variant_id is not None:
        if isinstance(variant_id, str):
            if variant_id.lower() not in ('null', 'undefined', ''):
                try:
                    actual_variant_id = int(variant_id)
                except ValueError:
                    print(f"DEBUG: Failed to parse variant_id: {variant_id}")
        else:
            try:
                actual_variant_id = int(variant_id)
            except (ValueError, TypeError):
                pass

    product = db.query(models.Product).filter(models.Product.id == product_id).first()
    if not product:
        print(f"DEBUG: Product {product_id} not found")
        raise HTTPException(status_code=404, detail="Product not found")
    
    if actual_variant_id:
        variant = db.query(models.ProductVariant).filter(models.ProductVariant.id == actual_variant_id, models.ProductVariant.product_id == product_id).first()
        if not variant:
            print(f"DEBUG: Variant {actual_variant_id} not found for product {product_id}")
            raise HTTPException(status_code=404, detail="Variant not found for this product")

    uploaded_images = []
    for file in images:
        print(f"DEBUG: Processing file: {file.filename}")
        if file and allowed_image_file(file.filename):
            ext = file.filename.rsplit('.', 1)[1].lower()
            filename = f"{uuid.uuid4()}.{ext}"
            file_path = os.path.join(UPLOAD_DIR, filename)
            
            # Ensure we are at the start of the file
            file.file.seek(0)
            
            with open(file_path, "wb") as buffer:
                shutil.copyfileobj(file.file, buffer)
            
            # Check if this product has ANY images yet
            total_product_images = db.query(models.ProductImage).filter(models.ProductImage.product_id == product_id).count()
            
            is_primary = False
            if total_product_images == 0 and not uploaded_images:
                is_primary = True

            img = models.ProductImage(
                product_id=product.id, 
                variant_id=actual_variant_id, 
                filename=filename, 
                is_primary=is_primary
            )
            db.add(img)
            uploaded_images.append(img)
            print(f"DEBUG: Saved image as {filename}")
        else:
            print(f"DEBUG: File rejected by allowed_image_file: {file.filename}")
    
    db.commit()
    print(f"DEBUG: Upload complete, saved {len(uploaded_images)} images")
    return {"msg": "Images uploaded", "images": [{"id": i.id, "filename": i.filename, "url": f"/uploads/products/{i.filename}", "is_primary": i.is_primary} for i in uploaded_images]}

# Variant Management Routes
@router.post("/{product_id}/variants")
def create_variant(
    product_id: int,
    data: schemas.ProductVariantBase,
    db: Session = Depends(get_db),
    current_admin: models.User = Depends(get_current_admin)
):
    product = db.query(models.Product).filter(models.Product.id == product_id).first()
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    
    variant = models.ProductVariant(
        product_id=product_id, 
        name=data.name, 
        price=data.price,
        stock=data.stock
    )
    db.add(variant)
    db.flush()
    sync_product_totals_from_variants(product)
    db.commit()
    db.refresh(product)
    db.refresh(variant)
    return {"msg": "Variant created", "variant": {"id": variant.id, "name": variant.name, "price": float(variant.price) if variant.price else None, "stock": variant.stock}}

@router.put("/{product_id}/variants/{variant_id}")
def update_variant(
    product_id: int,
    variant_id: int,
    data: schemas.ProductVariantBase,
    db: Session = Depends(get_db),
    current_admin: models.User = Depends(get_current_admin)
):
    variant = db.query(models.ProductVariant).filter(models.ProductVariant.id == variant_id, models.ProductVariant.product_id == product_id).first()
    if not variant:
        raise HTTPException(status_code=404, detail="Variant not found")
    
    variant.name = data.name
    variant.price = data.price
    variant.stock = data.stock
    sync_product_totals_from_variants(variant.product)
    db.commit()
    db.refresh(variant)
    return {"msg": "Variant updated", "variant": {"id": variant.id, "name": variant.name, "price": float(variant.price) if variant.price else None, "stock": variant.stock}}

@router.delete("/{product_id}/variants/{variant_id}")
def delete_variant(
    product_id: int,
    variant_id: int,
    db: Session = Depends(get_db),
    current_admin: models.User = Depends(get_current_admin)
):
    variant = db.query(models.ProductVariant).filter(models.ProductVariant.id == variant_id, models.ProductVariant.product_id == product_id).first()
    if not variant:
        raise HTTPException(status_code=404, detail="Variant not found")
    
    # Optional: Delete associated images from disk
    for img in variant.images:
        file_path = os.path.join(UPLOAD_DIR, img.filename)
        if os.path.exists(file_path):
            os.remove(file_path)

    db.delete(variant)
    db.flush()
    sync_product_totals_from_variants(db.query(models.Product).filter(models.Product.id == product_id).first())
    db.commit()
    return {"msg": "Variant deleted"}

@router.patch("/{product_id}/images/{image_id}/primary")
def set_primary_image(
    product_id: int,
    image_id: int,
    db: Session = Depends(get_db),
    current_admin: models.User = Depends(get_current_admin)
):
    product = db.query(models.Product).filter(models.Product.id == product_id).first()
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
        
    image = db.query(models.ProductImage).filter(models.ProductImage.id == image_id, models.ProductImage.product_id == product_id).first()
    if not image:
        raise HTTPException(status_code=404, detail="Image not found")
    
    # Reset all images to not primary
    db.query(models.ProductImage).filter(models.ProductImage.product_id == product_id).update({"is_primary": False})
    
    # Set this one as primary
    image.is_primary = True
    db.commit()
    
    return {"msg": "Primary image updated"}

@router.delete("/{product_id}/images/{image_id}")
def delete_image(
    product_id: int,
    image_id: int,
    db: Session = Depends(get_db),
    current_admin: models.User = Depends(get_current_admin)
):
    image = db.query(models.ProductImage).filter(models.ProductImage.id == image_id, models.ProductImage.product_id == product_id).first()
    if not image:
        raise HTTPException(status_code=404, detail="Image not found")
    
    # Delete file
    file_path = os.path.join(UPLOAD_DIR, image.filename)
    if os.path.exists(file_path):
        os.remove(file_path)
    
    was_primary = image.is_primary
    db.delete(image)
    db.commit()
    
    # If primary was deleted, set another one as primary if available
    if was_primary:
        next_img = db.query(models.ProductImage).filter(models.ProductImage.product_id == product_id).first()
        if next_img:
            next_img.is_primary = True
            db.commit()

    return {"msg": "Image deleted"}
