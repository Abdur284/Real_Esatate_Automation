from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.api.endpoints import chat, design_2d, design_3d, interior

app = FastAPI(
    title="Haven AI Backend",
    description="Backend for Haven AI with FastAPI",
    version="1.0.0"
)

# Configure CORS
origins = [
    "http://localhost:5173",
    "http://127.0.0.1:5173",
    "http://localhost:5000",   # Vite dev server (actual port)
    "http://127.0.0.1:5000",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["X-Bounds"],   # Interior Design: object sprite position
)

# Include Routers
app.include_router(chat.router, prefix="/api/chat", tags=["Chat"])
app.include_router(design_2d.router, prefix="/api/design/2d", tags=["2D Design"])
app.include_router(design_3d.router, prefix="/api/design/3d", tags=["3D Design"])
app.include_router(interior.router, prefix="/api/interior", tags=["Interior Design"])

@app.get("/")
async def root():
    return {"message": "Welcome to Haven AI API", "status": "running"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)
