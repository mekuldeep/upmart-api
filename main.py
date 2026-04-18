from fastapi import FastAPI, Request, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from database import engine, Base
import models
from routers import auth, categories, products, orders, customers, settings, store, coupons
import os

# Create database tables
models.Base.metadata.create_all(bind=engine)

app = FastAPI(title="Upmart B2B FastAPI")

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:8081",
        "http://localhost:8080",
        "http://localhost:8000",
        "http://localhost:5173",
        "http://localhost:5174",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Static files for uploads
UPLOAD_PATH = "uploads"
if not os.path.exists(UPLOAD_PATH):
    os.makedirs(UPLOAD_PATH)
    os.makedirs(os.path.join(UPLOAD_PATH, "products"))

app.mount("/uploads", StaticFiles(directory=UPLOAD_PATH), name="uploads")

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

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=5000, reload=True)
