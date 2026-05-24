from database import SessionLocal, engine, Base
import models
from utils.auth import get_password_hash
from datetime import datetime
from sqlalchemy import text

def seed():
    # Sync schema
    # Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    
    db = SessionLocal()
    try:
        # 1. Admin
        if not db.query(models.User).filter(models.User.email == 'admin@upmart.com').first():
            new_admin = models.User(
                email='admin@upmart.com', 
                name='Admin User',
                password_hash=get_password_hash('12345678'),
                is_admin=True
            )
            db.add(new_admin)
            print("Admin created: admin@upmart.com / 12345678")
        
        # 2. Categories
        # categories_data = [
        #     {"name": "Valves", "slug": "valves", "description": "Industrial valves"},
        #     {"name": "Pipes", "slug": "pipes", "description": "Steel and Pipes"},
        #     {"name": "Pumps", "slug": "pumps", "description": "Hydraulic and electric pumps"},
        #     {"name": "Instruments", "slug": "instruments", "description": "Measuring instruments"},
        #     {"name": "Couplings", "slug": "couplings", "description": "Flanged couplings"},
        #     {"name": "Fittings", "slug": "fittings", "description": "Stainless fittings"},
        #     {"name": "Motors", "slug": "motors", "description": "Electric motors"}
        # ]

        categories_data = [
            {"name": "Men", "slug": "men", "description": "Men's Apparel and Fashion"},
            {"name": "Women", "slug": "women", "description": "Women's Apparel and Fashion"},
            {"name": "Kids", "slug": "kids", "description": "Clothing for Kids"},
            {"name": "Accessories", "slug": "accessories", "description": "Jewelry, Bags, and more"},
        ]
        
        for cat_data in categories_data:
            if not db.query(models.Category).filter(models.Category.slug == cat_data["slug"]).first():
                cat = models.Category(**cat_data)
                db.add(cat)
        
        db.commit()
        print("Categories seeded")
        
        # 3. Products
        men_cat = db.query(models.Category).filter(models.Category.slug == 'men').first()
        women_cat = db.query(models.Category).filter(models.Category.slug == 'women').first()
        kids_cat = db.query(models.Category).filter(models.Category.slug == 'kids').first()
        accessories_cat = db.query(models.Category).filter(models.Category.slug == 'accessories').first()
        
        products_data = [
            {"name": "Classic Derby Formal Shoes", "sku": "M-DERBY-001", "price": 1299.00, "description": "Premium leather derby shoes perfect for office and formal occasions.", "stock": 145, "category_id": men_cat.id, "status": "active"},
            {"name": "Leather Penny Loafers", "sku": "M-LOAFER-002", "price": 1099.00, "description": "Handcrafted penny loafers with premium leather. Perfect for semi-formal wear.", "stock": 320, "category_id": men_cat.id, "status": "active", "is_group_order_enabled": True, "group_size": 5},
            {"name": "Strappy Block Heel Sandals", "sku": "W-HEEL-001", "price": 1199.00, "description": "Elegant strappy sandals with comfortable block heels.", "stock": 28, "category_id": women_cat.id, "status": "active"},
            {"name": "Running Sneakers", "sku": "W-SNEAK-003", "price": 999.00, "description": "Lightweight running sneakers with breathable mesh upper.", "stock": 580, "category_id": women_cat.id, "status": "active", "min_order_qty": 10},
            {"name": "Velcro School Shoes", "sku": "K-SCHOOL-001", "price": 599.00, "description": "Durable school shoes with easy velcro closure.", "stock": 92, "category_id": kids_cat.id, "status": "active"},
            {"name": "Colorful Sports Sneakers", "sku": "K-SPORT-002", "price": 699.00, "description": "Fun and colorful sports sneakers with excellent grip.", "stock": 67, "category_id": kids_cat.id, "status": "active"},
            {"name": "Premium Shoe Care Kit", "sku": "A-CARE-001", "price": 499.00, "description": "Complete shoe care kit with polish, brush, and conditioner.", "stock": 1200, "category_id": accessories_cat.id, "status": "active", "is_group_order_enabled": True, "group_size": 12},
            {"name": "Cotton Socks Pack (5 Pairs)", "sku": "A-SOCK-002", "price": 299.00, "description": "Premium cotton socks in assorted colors.", "stock": 500, "category_id": accessories_cat.id, "status": "active"}
        ]
        
        for prod_data in products_data:
            if not db.query(models.Product).filter(models.Product.sku == prod_data["sku"]).first():
                prod = models.Product(**prod_data)
                db.add(prod)
        
        db.commit()
        print("Products seeded")
        
        # 4. Customers (Regular Users)
        customers_data = [
            {"name": "Acme Corp", "email": "purchasing@acme.com", "company": "Acme Corporation", "password_hash": get_password_hash('password123')},
            {"name": "BuildRight Inc", "email": "orders@buildright.com", "company": "BuildRight Industries", "password_hash": get_password_hash('password123')},
            {"name": "Metro Supply Co", "email": "info@metrosupply.com", "company": "Metro Supply Company", "password_hash": get_password_hash('password123')},
            {"name": "Pacific Industrial", "email": "buy@pacific-ind.com", "company": "Pacific Industrial Ltd", "password_hash": get_password_hash('password123')},
            {"name": "Northern Fabrication", "email": "orders@northfab.com", "company": "Northern Fabrication LLC", "password_hash": get_password_hash('password123')}
        ]
        
        for cust_data in customers_data:
            if not db.query(models.User).filter(models.User.email == cust_data["email"]).first():
                cust = models.User(**cust_data, is_admin=False)
                db.add(cust)
        
        db.commit()
        print("Customers seeded")
        
        # 5. Orders
        acme = db.query(models.User).filter(models.User.name == "Acme Corp").first()
        derby = db.query(models.Product).filter(models.Product.sku == "M-DERBY-001").first()
        
        if acme and derby and not db.query(models.Order).first():
            order = models.Order(
                order_number="ORD-20240404001",
                user_id=acme.id,
                total=derby.price * 2,
                status="delivered"
            )
            db.add(order)
            db.commit()
            db.refresh(order)
            
            order_item = models.OrderItem(
                order_id=order.id,
                product_id=derby.id,
                quantity=2,
                unit_price=derby.price
            )
            db.add(order_item)
            db.commit()
            print("Sample order created")
            
    finally:
        db.close()

if __name__ == '__main__':
    seed()
