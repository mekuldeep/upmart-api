from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, Form
from sqlalchemy.orm import Session
from database import get_db
import models, schemas
from routers.auth import get_current_admin
from typing import List, Optional
import os
import uuid
import shutil

router = APIRouter(prefix="/products", tags=["products"])

UPLOAD_DIR = "uploads/products"
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
    ALLOWED_EXTENSIONS = {'jpg', 'jpeg', 'png', 'webp'}
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

@router.get("")
def list_products(
    page: int = 1,
    search: str = "",
    category_id: Optional[int] = None,
    status: Optional[str] = None,
    db: Session = Depends(get_db),
    current_admin: models.User = Depends(get_current_admin)
):
    query = db.query(models.Product).join(models.Product.category, isouter=True)

    if search:
        query = query.filter(
            models.Product.name.ilike(f'%{search}%') | 
            models.Product.sku.ilike(f'%{search}%') |
            models.Category.name.ilike(f'%{search}%')
        )
    
    if category_id:
        query = query.filter(models.Product.category_id == category_id)
    
    if status:
        query = query.filter(models.Product.status == status)

    paginated = paginate_query(query.order_by(models.Product.created_at.desc()), page)
    
    products_data = []
    for p in paginated['items']:
        # Get all variants for the product
        variants_data = []
        for v in p.variants:
            v_images = [{"id": img.id, "filename": img.filename, "is_primary": img.is_primary, "url": f"/uploads/products/{img.filename}", "variant_id": img.variant_id} for img in v.images]
            variants_data.append({
                "id": v.id,
                "name": v.name,
                "images": v_images
            })

        # Product-level images (if any remain)
        product_images = [{"id": img.id, "filename": img.filename, "is_primary": img.is_primary, "url": f"/uploads/products/{img.filename}", "variant_id": img.variant_id} for img in p.images if not img.variant_id]
        
        # Primary image logic: 
        # 1. Product-level primary 
        # 2. First variant's primary image
        # 3. First variant's first image
        # 4. First product-level image
        primary_image = next((img for img in product_images if img['is_primary']), None)
        if not primary_image and variants_data:
            for v in variants_data:
                primary_image = next((img for img in v['images'] if img['is_primary']), None)
                if primary_image: break
            if not primary_image and variants_data[0]['images']:
                primary_image = variants_data[0]['images'][0]
        if not primary_image and product_images:
            primary_image = product_images[0]
        
        products_data.append({
            "id": p.id,
            "name": p.name,
            "sku": p.sku,
            "description": p.description,
            "price": float(p.price),
            "stock": p.stock,
            "category_id": p.category_id,
            "category_name": p.category.name if p.category else None,
            "status": p.status,
            "min_order_qty": p.min_order_qty,
            "is_group_order_enabled": p.is_group_order_enabled,
            "group_size": p.group_size,
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
    if db.query(models.Product).filter(models.Product.sku == data.sku).first():
        raise HTTPException(status_code=400, detail="Product with this SKU already exists")

    product_data = data.dict()
    variants_data = product_data.pop('variants', [])
    
    product = models.Product(**product_data)
    db.add(product)
    db.commit()
    db.refresh(product)
    
    # Create variants if provided
    created_variants = []
    for v_data in variants_data:
        variant = models.ProductVariant(product_id=product.id, name=v_data['name'])
        db.add(variant)
        created_variants.append(variant)
    
    if variants_data:
        db.commit()
        for v in created_variants:
            db.refresh(v)
        db.refresh(product)

    return {
        "msg": "Product created", 
        "product": {
            "id": product.id,
            "name": product.name,
            "sku": product.sku,
            "variants": [{"id": v.id, "name": v.name} for v in created_variants]
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
            "images": v_images
        })

    product_images = [{"id": img.id, "filename": img.filename, "is_primary": img.is_primary, "url": f"/uploads/products/{img.filename}", "variant_id": img.variant_id} for img in product.images if not img.variant_id]
    
    # Primary image logic (re-using same logic)
    primary_image = next((img for img in product_images if img['is_primary']), None)
    if not primary_image and variants_data:
        for v in variants_data:
            primary_image = next((img for img in v['images'] if img['is_primary']), None)
            if primary_image: break
        if not primary_image and variants_data[0]['images']:
            primary_image = variants_data[0]['images'][0]
    if not primary_image and product_images:
        primary_image = product_images[0]

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
            "status": product.status,
            "min_order_qty": product.min_order_qty,
            "is_group_order_enabled": product.is_group_order_enabled,
            "group_size": product.group_size,
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
    data: dict,
    db: Session = Depends(get_db),
    current_admin: models.User = Depends(get_current_admin)
):
    product = db.query(models.Product).filter(models.Product.id == product_id).first()
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")

    if 'sku' in data and data['sku'] != product.sku:
        if db.query(models.Product).filter(models.Product.sku == data['sku']).first():
            raise HTTPException(status_code=400, detail="Product with this SKU already exists")

    for key, value in data.items():
        if hasattr(product, key):
            setattr(product, key, value)

    db.commit()
    db.refresh(product)
    return {"msg": "Product updated", "product": product}

@router.delete("/{product_id}")
def delete_product(
    product_id: int,
    db: Session = Depends(get_db),
    current_admin: models.User = Depends(get_current_admin)
):
    product = db.query(models.Product).filter(models.Product.id == product_id).first()
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    
    db.delete(product)
    db.commit()
    return {"msg": "Product deleted"}

@router.post("/{product_id}/images")
def upload_images(
    product_id: int,
    variant_id: Optional[int] = Form(None),
    images: List[UploadFile] = File(...),
    db: Session = Depends(get_db),
    current_admin: models.User = Depends(get_current_admin)
):
    product = db.query(models.Product).filter(models.Product.id == product_id).first()
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    
    if variant_id:
        variant = db.query(models.ProductVariant).filter(models.ProductVariant.id == variant_id, models.ProductVariant.product_id == product_id).first()
        if not variant:
            raise HTTPException(status_code=404, detail="Variant not found for this product")

    uploaded_images = []
    for file in images:
        if file and allowed_image_file(file.filename):
            ext = file.filename.rsplit('.', 1)[1].lower()
            filename = f"{uuid.uuid4()}.{ext}"
            file_path = os.path.join(UPLOAD_DIR, filename)
            
            with open(file_path, "wb") as buffer:
                shutil.copyfileobj(file.file, buffer)
            
            # Check if this is the first image for this product or variant, if so make it primary
            is_primary = False
            if variant_id:
                image_count = db.query(models.ProductImage).filter(models.ProductImage.variant_id == variant_id).count()
            else:
                image_count = db.query(models.ProductImage).filter(models.ProductImage.product_id == product_id, models.ProductImage.variant_id == None).count()
            
            if image_count == 0 and not uploaded_images:
                is_primary = True

            img = models.ProductImage(
                product_id=product.id, 
                variant_id=variant_id, 
                filename=filename, 
                is_primary=is_primary
            )
            db.add(img)
            uploaded_images.append(img)
    
    db.commit()
    return {"msg": "Images uploaded", "images": [{"id": i.id, "filename": i.filename, "is_primary": i.is_primary} for i in uploaded_images]}

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
    
    variant = models.ProductVariant(product_id=product_id, name=data.name)
    db.add(variant)
    db.commit()
    db.refresh(variant)
    return {"msg": "Variant created", "variant": {"id": variant.id, "name": variant.name}}

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
    db.commit()
    return {"msg": "Variant updated", "variant": {"id": variant.id, "name": variant.name}}

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
