from fastapi import FastAPI, Request, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse
from sqlalchemy.exc import SQLAlchemyError
from database import engine, Base
import models
from routers import auth, categories, products, orders, customers, settings, store, coupons
import os
import mimetypes
import logging

logger = logging.getLogger(__name__)

# Create database tables
# try:
#     models.Base.metadata.create_all(bind=engine)
# except Exception as e:
#     print("Tables already exist, skipping...")

app = FastAPI(title="Upmart B2B FastAPI")

CORS_ALLOW_ORIGINS = [
    "http://localhost:8081",
    "http://localhost:8080",
    "http://localhost:8000",
    "http://localhost:5000",
    "http://localhost:5173",
    "http://localhost:5174",
    "http://127.0.0.1:8081",
    "http://127.0.0.1:8080",
    "http://127.0.0.1:8000",
    "http://127.0.0.1:5000",
    "http://127.0.0.1:5173",
    "http://127.0.0.1:5174",
    "https://upmart-admin.vercel.app",
    "https://upmart-frontend.vercel.app",
    "https://upmart.co.in",
    "https://www.upmart.co.in",
    "https://admin.upmart.co.in",
    "https://www.admin.upmart.co.in",
    "http://upmart.co.in",
    "http://www.upmart.co.in",
    "http://admin.upmart.co.in",
    "http://www.admin.upmart.co.in",
]

CORS_ALLOW_ORIGIN_REGEX = (
    r"https://.*\.ngrok-free\.app|"
    r"https://.*\.vercel\.app|"
    r"http://localhost:.*|"
    r"http://127\.0\.0\.1:.*|"
    r"https?://(.*\.)?upmart\.co\.in"
)

@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": exc.detail},
        headers=getattr(exc, "headers", None),
    )

@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    logger.exception("Unhandled API error on %s %s", request.method, request.url.path)
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error"},
    )

@app.exception_handler(SQLAlchemyError)
async def sqlalchemy_exception_handler(request: Request, exc: SQLAlchemyError):
    logger.exception("Database error on %s %s", request.method, request.url.path)
    return JSONResponse(
        status_code=500,
        content={"detail": "Database error"},
    )

# Static files for uploads
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
UPLOAD_PATH = os.path.join(BASE_DIR, "uploads")

if not os.path.exists(UPLOAD_PATH):
    os.makedirs(UPLOAD_PATH)
    os.makedirs(os.path.join(UPLOAD_PATH, "products"))

# ─── Image serving route (fixes blank images on other devices via ngrok) ──────
# <img> tags cannot send HTTP request headers (like ngrok-skip-browser-warning),
# so ngrok shows its interstitial HTML instead of the actual image.
# The fix: serve images through a FastAPI route that explicitly sets the correct
# Content-Type and adds the ngrok bypass response header, so ngrok never
# intercepts the response with its warning page.
@app.get("/uploads/{subpath:path}")
async def serve_upload(subpath: str):
    file_path = os.path.join(UPLOAD_PATH, subpath)
    if not os.path.exists(file_path) or not os.path.isfile(file_path):
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="File not found")

    # Detect correct content type
    content_type, _ = mimetypes.guess_type(file_path)
    if not content_type:
        content_type = "application/octet-stream"

    response = FileResponse(
        path=file_path,
        media_type=content_type,
    )
    # KEY FIX: These response headers tell ngrok to skip its browser warning page,
    # so images load correctly for ANY device — no request header needed.
    response.headers["ngrok-skip-browser-warning"] = "true"
    response.headers["Bypass-Tunnel-Reminder"] = "true"
    response.headers["Cache-Control"] = "public, max-age=3600"
    return response

# Include routers
app.include_router(auth.router, prefix="/api")
app.include_router(categories.router, prefix="/api")
app.include_router(products.router, prefix="/api")
app.include_router(orders.router, prefix="/api")
app.include_router(customers.router, prefix="/api")
app.include_router(settings.router, prefix="/api")
app.include_router(store.router, prefix="/api")
app.include_router(coupons.router, prefix="/api")

@app.get("/")
def read_root():
    return {"message": "Upmart B2B FastAPI is running!"}

# Keep CORS as the outermost ASGI wrapper so error responses also include
# Access-Control-Allow-Origin instead of looking like browser CORS failures.
app = CORSMiddleware(
    app,
    allow_origins=CORS_ALLOW_ORIGINS,
    allow_origin_regex=CORS_ALLOW_ORIGIN_REGEX,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

if __name__ == "__main__":
    import uvicorn
    # Use port 8000 to match the ngrok configuration
    print("Starting server on port 8000...")
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
