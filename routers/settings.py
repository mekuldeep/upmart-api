from fastapi import APIRouter, Depends
import models
from routers.auth import get_current_admin
import os
import json

router = APIRouter(prefix="/settings", tags=["settings"])

SETTINGS_FILE = os.getenv("SETTINGS_FILE", "settings.json")

DEFAULT_SETTINGS = {
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
    "brands": "Nike, Adidas, Puma, Reebok, Levi's, Zara, H&M"
}

REMOVED_SETTINGS = {"siteName", "logo_url"}

def load_settings():
    if os.path.exists(SETTINGS_FILE):
        try:
            with open(SETTINGS_FILE, "r") as f:
                data = json.load(f)
                for key in REMOVED_SETTINGS:
                    data.pop(key, None)
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

@router.get("")
@router.get("/")
def get_settings():
    return load_settings()

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
