from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from database import get_db
import models, schemas
from routers.auth import get_current_admin
import re
from typing import List, Optional

router = APIRouter(prefix="/categories", tags=["categories"])

def slugify(text):
    text = text.lower().strip()
    text = re.sub(r'[^\w\s-]', '', text)
    text = re.sub(r'[\s_-]+', '-', text)
    return text

def category_product_count(db: Session, category_id: int) -> int:
    return db.query(models.Product).filter(models.Product.category_id == category_id).count()

def category_to_dict(db: Session, c: models.Category, include_children: bool = False):
    result = {
        "id": c.id,
        "name": c.name,
        "slug": c.slug,
        "description": c.description,
        "parent_id": c.parent_id,
        "sort_order": c.sort_order or 0,
        "is_active": True if c.is_active is None else c.is_active,
        "product_count": category_product_count(db, c.id),
        "created_at": c.created_at
    }
    if include_children:
        children = sorted(c.children, key=lambda child: (child.sort_order or 0, child.name.lower()))
        result["children"] = [category_to_dict(db, child, include_children=True) for child in children]
    return result

def validate_parent(db: Session, parent_id: Optional[int], category_id: Optional[int] = None):
    if not parent_id:
        return None
    if category_id and parent_id == category_id:
        raise HTTPException(status_code=400, detail="Category cannot be its own parent")
    parent = db.query(models.Category).filter(models.Category.id == parent_id).first()
    if not parent:
        raise HTTPException(status_code=400, detail="Parent category not found")
    if parent.parent_id:
        raise HTTPException(status_code=400, detail="Only main categories can be selected as parent")
    return parent_id

@router.get("")
def list_categories(
    db: Session = Depends(get_db), 
    current_admin: models.User = Depends(get_current_admin)
):
    categories = db.query(models.Category).filter(models.Category.parent_id == None).order_by(models.Category.sort_order, models.Category.name).all()

    return {
        "categories": [category_to_dict(db, c, include_children=True) for c in categories],
        "total": db.query(models.Category).count()
    }

@router.get("/all")
def list_all_flat(
    db: Session = Depends(get_db), 
    current_admin: models.User = Depends(get_current_admin)
):
    categories = db.query(models.Category).order_by(models.Category.sort_order, models.Category.name).all()
    return {"categories": [category_to_dict(db, c) for c in categories]}

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

    parent_id = validate_parent(db, data.parent_id)
    category = models.Category(
        name=data.name,
        slug=slug,
        description=data.description,
        parent_id=parent_id,
        sort_order=data.sort_order or 0,
        is_active=data.is_active
    )
    db.add(category)
    db.commit()
    db.refresh(category)
    return {"msg": "Category created", "category": category_to_dict(db, category)}

def save_category_order(
    items: List[dict],
    db: Session = Depends(get_db),
    current_admin: models.User = Depends(get_current_admin)
):
    for item in items:
        category_id = item.get("id")
        if category_id is None:
            continue
        category = db.query(models.Category).filter(models.Category.id == category_id).first()
        if category:
            category.sort_order = int(item.get("sort_order") or 0)
    db.commit()
    return {"msg": "Category order updated"}

@router.post("/reorder")
def reorder_categories_post(
    items: List[dict],
    db: Session = Depends(get_db),
    current_admin: models.User = Depends(get_current_admin)
):
    return save_category_order(items, db, current_admin)

@router.patch("/reorder")
def reorder_categories_patch(
    items: List[dict],
    db: Session = Depends(get_db),
    current_admin: models.User = Depends(get_current_admin)
):
    return save_category_order(items, db, current_admin)

@router.get("/{category_id}")
def get_category(
    category_id: int, 
    db: Session = Depends(get_db), 
    current_admin: models.User = Depends(get_current_admin)
):
    category = db.query(models.Category).filter(models.Category.id == category_id).first()
    if not category:
        raise HTTPException(status_code=404, detail="Category not found")
    
    return {"category": category_to_dict(db, category, include_children=True)}

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
        category.parent_id = validate_parent(db, data['parent_id'], category_id)

    if 'sort_order' in data:
        category.sort_order = int(data['sort_order'] or 0)

    if 'is_active' in data:
        category.is_active = bool(data['is_active'])

    db.commit()
    db.refresh(category)
    return {"msg": "Category updated", "category": category_to_dict(db, category)}

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
