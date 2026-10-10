import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.endpoints import admin, auth, chat, cost, design_2d, design_3d, interior, properties
from app.core.config import settings

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")

app = FastAPI(
    title="Haven AI Backend",
    description="Backend for Haven AI with FastAPI",
    version="1.0.0"
)

# Allowed browser origins come from CORS_ORIGINS in .env (see config.py).
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["X-Bounds"],   # Interior Design: object sprite position
)

# Include Routers
app.include_router(chat.router, prefix="/api/chat", tags=["Chat"])
app.include_router(cost.router, prefix="/api/cost", tags=["Cost Estimation"])
app.include_router(design_2d.router, prefix="/api/design/2d", tags=["2D Design"])
app.include_router(design_3d.router, prefix="/api/design/3d", tags=["3D Design"])
app.include_router(interior.router, prefix="/api/interior", tags=["Interior Design"])
app.include_router(admin.router, prefix="/api/admin", tags=["Admin"])
app.include_router(auth.router, prefix="/api/auth", tags=["Account"])
app.include_router(properties.router, prefix="/api/properties", tags=["Properties"])

@app.get("/")
async def root():
    return {"message": "Welcome to Haven AI API", "status": "running"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)
