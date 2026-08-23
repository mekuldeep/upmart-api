from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
import models
from routers.auth import get_current_admin
import os
import json
from pathlib import Path
from utils.file_security import save_validated_image

router = APIRouter(prefix="/settings", tags=["settings"])

UPLOAD_DIR = "uploads/settings"
if not os.path.exists(UPLOAD_DIR):
    os.makedirs(UPLOAD_DIR, exist_ok=True)

SETTINGS_FILE = os.getenv("SETTINGS_FILE", "settings.json")

DEFAULT_SETTINGS = {
    "siteName": "Upmart",
    "siteEmail": "support@upmart.com",
    "taxRate": "18",
    "minOrder": "100",
    "facebook": "https://facebook.com/upmart",
    "instagram": "https://instagram.com/upmart",
    "twitter": "https://twitter.com/upmart",
    "youtube": "https://youtube.com/upmart",
    "address": "123 Business Park, Sector 62",
    "city": "Noida",
    "state": "Uttar Pradesh",
    "zip": "201301",
    "phone": "+91 98765 43210",
    "email": "contact@upmart.com",
    "brands": "Nike, Adidas, Puma, Reebok, Levi's, Zara, H&M",
    "logo_url": None
}

def load_settings():
    if os.path.exists(SETTINGS_FILE):
        try:
            with open(SETTINGS_FILE, "r") as f:
                data = json.load(f)
                # Ensure all default keys exist
                for k, v in DEFAULT_SETTINGS.items():
                    if k not in data:
                        data[k] = v
                return data
        except Exception:
            return DEFAULT_SETTINGS.copy()
    return DEFAULT_SETTINGS.copy()

def save_settings(data):
    with open(SETTINGS_FILE, "w") as f:
        json.dump(data, f, indent=4)

@router.post("/logo")
@router.post("/logo/")
async def upload_logo(
    file: UploadFile = File(...),
    current_admin: models.User = Depends(get_current_admin)
):
    upload_path = Path(UPLOAD_DIR)
    file_name = save_validated_image(file, upload_path, filename_stem="logo")
    for old_logo in upload_path.glob("logo.*"):
        if old_logo.is_file() and old_logo.name != file_name:
            old_logo.unlink()
    
    logo_path = f"/uploads/settings/{file_name}"
    
    # Save logo path in settings.json
    settings = load_settings()
    settings["logo_url"] = logo_path
    save_settings(settings)
    
    return {"logo_url": logo_path}

@router.get("")
@router.get("/")
def get_settings():
    settings = load_settings()
    # Check if logo file exists, otherwise set to None
    if settings.get("logo_url"):
        local_path = settings["logo_url"].lstrip("/")
        if not os.path.exists(local_path):
            settings["logo_url"] = None
    return settings

@router.put("")
@router.put("/")
def update_settings(
    data: dict,
    current_admin: models.User = Depends(get_current_admin)
):
    current = load_settings()
    for k, v in data.items():
        if k in DEFAULT_SETTINGS:
            current[k] = v
    save_settings(current)
    return current
