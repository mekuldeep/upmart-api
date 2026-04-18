from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from database import get_db
import models, schemas
from routers.auth import get_current_admin
import re
from typing import List

router = APIRouter(prefix="/categories", tags=["categories"])

def slugify(text):
    text = text.lower().strip()
    text = re.sub(r'[^\w\s-]', '', text)
    text = re.sub(r'[\s_-]+', '-', text)
    return text

@router.get("")
def list_categories(
    db: Session = Depends(get_db), 
    current_admin: models.User = Depends(get_current_admin)
):
    categories = db.query(models.Category).filter(models.Category.parent_id == None).order_by(models.Category.name).all()
    # Manual serialization since we need include_children logic which is easier to handle here or in schema
    def category_to_dict(c):
        result = {
            "id": c.id,
            "name": c.name,
            "slug": c.slug,
            "description": c.description,
            "parent_id": c.parent_id,
            "product_count": db.query(models.Product).filter(models.Product.category_id == c.id).count(),
            "created_at": c.created_at
        }
        result["children"] = [category_to_dict(child) for child in c.children]
        return result

    return {
        "categories": [category_to_dict(c) for c in categories],
        "total": db.query(models.Category).count()
    }

@router.get("/all")
def list_all_flat(
    db: Session = Depends(get_db), 
    current_admin: models.User = Depends(get_current_admin)
):
    categories = db.query(models.Category).order_by(models.Category.name).all()
    return {"categories": [{
        "id": c.id,
        "name": c.name,
        "slug": c.slug,
        "description": c.description,
        "parent_id": c.parent_id,
        "product_count": db.query(models.Product).filter(models.Product.category_id == c.id).count(),
        "created_at": c.created_at
    } for c in categories]}

@router.post("", status_code=status.HTTP_201_CREATED)
def create_category(
    data: schemas.CategoryCreate, 
    db: Session = Depends(get_db), 
    current_admin: models.User = Depends(get_current_admin)
):
    slug = slugify(data.slug or data.name)
    
    # Ensure slug is unique
    base_slug = slug
    counter = 1
    while db.query(models.Category).filter(models.Category.slug == slug).first():
        slug = f"{base_slug}-{counter}"
        counter += 1

    category = models.Category(
        name=data.name,
        slug=slug,
        description=data.description,
        parent_id=data.parent_id
    )
    db.add(category)
    db.commit()
    db.refresh(category)
    return {"msg": "Category created", "category": {
        "id": category.id,
        "name": category.name,
        "slug": category.slug,
        "description": category.description,
        "parent_id": category.parent_id
    }}

@router.get("/{category_id}")
def get_category(
    category_id: int, 
    db: Session = Depends(get_db), 
    current_admin: models.User = Depends(get_current_admin)
):
    category = db.query(models.Category).filter(models.Category.id == category_id).first()
    if not category:
        raise HTTPException(status_code=404, detail="Category not found")
    
    def category_to_dict(c):
        return {
            "id": c.id,
            "name": c.name,
            "slug": c.slug,
            "description": c.description,
            "parent_id": c.parent_id,
            "product_count": db.query(models.Product).filter(models.Product.category_id == c.id).count(),
            "created_at": c.created_at,
            "children": [category_to_dict(child) for child in c.children]
        }
    
    return {"category": category_to_dict(category)}

@router.put("/{category_id}")
def update_category(
    category_id: int, 
    data: dict, 
    db: Session = Depends(get_db), 
    current_admin: models.User = Depends(get_current_admin)
):
    category = db.query(models.Category).filter(models.Category.id == category_id).first()
    if not category:
        raise HTTPException(status_code=404, detail="Category not found")
    
    if 'name' in data:
        name = data['name'].strip()
        if not name:
            raise HTTPException(status_code=400, detail="Category name cannot be empty")
        category.name = name

    if 'description' in data:
        category.description = data['description'].strip() or None

    if 'parent_id' in data:
        parent_id = data['parent_id']
        if parent_id == category_id:
            raise HTTPException(status_code=400, detail="Category cannot be its own parent")
        category.parent_id = parent_id or None

    db.commit()
    db.refresh(category)
    return {"msg": "Category updated", "category": {
        "id": category.id,
        "name": category.name,
        "slug": category.slug,
        "description": category.description,
        "parent_id": category.parent_id
    }}

@router.delete("/{category_id}")
def delete_category(
    category_id: int, 
    db: Session = Depends(get_db), 
    current_admin: models.User = Depends(get_current_admin)
):
    category = db.query(models.Category).filter(models.Category.id == category_id).first()
    if not category:
        raise HTTPException(status_code=404, detail="Category not found")
    
    product_count = db.query(models.Product).filter(models.Product.category_id == category_id).count()
    if product_count > 0:
        raise HTTPException(status_code=409, detail="Cannot delete category with associated products")
    
    db.delete(category)
    db.commit()
    return {"msg": "Category deleted"}
