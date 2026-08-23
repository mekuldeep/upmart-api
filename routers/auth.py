from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import func
from database import get_db
import models, schemas
from utils.auth import ALGORITHM, SECRET_KEY, create_access_token, get_password_hash, verify_password
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt

router = APIRouter(prefix="/admin", tags=["auth"])

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="api/admin/login")

def get_current_admin(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)):
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id: str = payload.get("sub")
        if user_id is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception
    user = db.query(models.User).filter(models.User.id == int(user_id)).first()
    if user is None or not user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to access admin panel"
        )
    return user

@router.post("/login")
def login(data: schemas.LoginRequest, db: Session = Depends(get_db)):
    try:
        user = db.query(models.User).filter(models.User.email == data.email, models.User.is_admin == True).first()
        
        if not user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid admin email or password",
                headers={"WWW-Authenticate": "Bearer"},
            )
            
        is_valid = verify_password(data.password, user.password_hash)
        
        if not is_valid:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid admin email or password",
                headers={"WWW-Authenticate": "Bearer"},
            )
            
        access_token = create_access_token(data={"sub": str(user.id)})
        return {
            "access_token": access_token,
            "admin": {
                "id": user.id,
                "email": user.email,
                "name": user.name,
                "is_admin": user.is_admin
            }
        }
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(status_code=500, detail="Internal server error")

@router.post("/change-password")
def change_password(
    data: schemas.AdminPasswordChange,
    current_admin: models.User = Depends(get_current_admin), 
    db: Session = Depends(get_db)
):
    if not verify_password(data.current_password, current_admin.password_hash):
        raise HTTPException(status_code=403, detail="Incorrect current password")
    
    current_admin.password_hash = get_password_hash(data.new_password)
    db.commit()
    
    return {"msg": "Password updated successfully"}

@router.put("/profile")
def update_admin_profile(
    data: dict,
    current_admin: models.User = Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    current_admin.name = data.get('name', current_admin.name)
    current_admin.email = data.get('email', current_admin.email)
    
    db.commit()
    db.refresh(current_admin)
    
    return {
        "msg": "Profile updated successfully",
        "admin": {
            "id": current_admin.id,
            "email": current_admin.email,
            "name": current_admin.name,
            "is_admin": current_admin.is_admin
        }
    }

@router.get("/stats")
def get_stats(
    current_admin: models.User = Depends(get_current_admin), 
    db: Session = Depends(get_db)
):
    product_count = db.query(models.Product).count()
    order_count = db.query(models.Order).count()
    customer_count = db.query(models.User).filter(models.User.is_admin == False).count()
    
    revenue = db.query(func.sum(models.Order.total)).scalar() or 0
    
    return {
        "product_count": product_count,
        "order_count": order_count,
        "customer_count": customer_count,
        "revenue": float(revenue)
    }
