from database import SessionLocal
import models
from datetime import datetime, timedelta

def seed_coupon():
    db = SessionLocal()
    try:
        # Create a percentage coupon
        code_pct = "SAVE10"
        if not db.query(models.Coupon).filter(models.Coupon.code == code_pct).first():
            coupon = models.Coupon(
                code=code_pct,
                description="10% discount on all orders",
                discount_type='percentage',
                discount_value=10.0,
                min_order_amount=100.0,
                is_active=True
            )
            db.add(coupon)
            print(f"Coupon created: {code_pct}")

        # Create a fixed coupon
        code_fix = "FLAT500"
        if not db.query(models.Coupon).filter(models.Coupon.code == code_fix).first():
            coupon = models.Coupon(
                code=code_fix,
                description="Flat ₹500 discount",
                discount_type='fixed',
                discount_value=500.0,
                min_order_amount=1000.0,
                is_active=True
            )
            db.add(coupon)
            print(f"Coupon created: {code_fix}")

        db.commit()
    except Exception as e:
        print(f"Error: {e}")
        db.rollback()
    finally:
        db.close()

if __name__ == "__main__":
    seed_coupon()
