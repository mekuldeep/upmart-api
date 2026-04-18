from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from sqlalchemy.orm import Session
from database import get_db
import models
from routers.auth import get_current_admin
import os
import shutil

router = APIRouter(prefix="/settings", tags=["settings"])

UPLOAD_DIR = "uploads/settings"
if not os.path.exists(UPLOAD_DIR):
    os.makedirs(UPLOAD_DIR)

@router.post("/logo")
async def upload_logo(
    file: UploadFile = File(...),
    current_admin: models.User = Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    # Only allow images
    if not file.content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="Only image files are allowed")
    
    # Save file as logo.png (overwrite previous)
    file_extension = file.filename.split(".")[-1]
    file_path = f"logo.{file_extension}"
    full_path = os.path.join(UPLOAD_DIR, file_path)
    
    with open(full_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)
    
    # In a real app, you might save this path in a Settings table
    # For now, we'll just return the path
    return {"logo_url": f"/uploads/settings/{file_path}"}

@router.get("")
def get_settings(
    db: Session = Depends(get_db)
):
    # Dummy settings for now
    return {
        "site_name": "Upmart",
        "logo_url": "/uploads/settings/logo.png" if os.path.exists("uploads/settings/logo.png") else None,
        "contact_email": "support@upmart.com"
    }
