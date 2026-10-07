import json
from typing import Annotated, List

from pydantic import field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(case_sensitive=True, extra="ignore", env_file=".env")

    PROJECT_NAME: str = "Haven AI"
    API_V1_STR: str = "/api"
    # Browser origins allowed to call the API. In .env either a JSON list or a
    # comma separated string: CORS_ORIGINS=https://haven.example.com,http://localhost:5000
    CORS_ORIGINS: Annotated[List[str], NoDecode] = [
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:5000",
        "http://127.0.0.1:5000",
    ]

    # Requests per minute per caller (signed-in uid, else client IP) on the
    # endpoints that call Gemini or do heavy CPU work. 0 disables the limit.
    RATE_LIMIT_PER_MINUTE: int = 20

    # API keys for ML services
    GEMINI_API_KEY: str = ""
    # Model for the chatbot, and the ordered fallback list for the 2D planner
    # (comma separated; empty = GEMINI_MODEL, gemini-3.8-flash, gemini-flash-latest).
    GEMINI_MODEL: str = "gemini-3.6-flash"
    GEMINI_MODELS_2D: str = ""
    # 3D Design photo analysis: "builtin" uses local code only (no AI service);
    # "gemini" uses Gemini vision plus the settings below.
    DESIGN3D_PHOTO_ANALYZER: str = "builtin"
    # Gemini analyser only: models that read the uploaded property photo, and
    # image-generation models for the optional photorealistic render (the
    # latter have no free-tier quota; they need billing on the Google project).
    GEMINI_VISION_MODELS: str = ""
    GEMINI_IMAGE_MODELS: str = "gemini-3.1-flash-image,gemini-2.5-flash-image"

    # Interior Design: local room segmentation model (ONNX, runs on CPU),
    # and where uploaded rooms and their edit history are kept.
    INTERIOR_SEG_MODEL_DIR: str = "ml_models/segformer-b2-ade"
    INTERIOR_STORAGE_DIR: str = "storage/interior"
    # Unsaved rooms are deleted after this many hours.
    INTERIOR_SCENE_TTL_HOURS: int = 24
    # Real-world 3D models and PBR textures of the object library (CC0, from
    # Poly Haven; fetched by scripts/fetch_interior_assets.py).
    INTERIOR_ASSET_DIR: str = "assets/interior"
    FIREBASE_CREDS_PATH: str = "firebase-credentials.json"

    @field_validator("CORS_ORIGINS", mode="before")
    @classmethod
    def _split_origins(cls, value):
        if isinstance(value, str):
            value = value.strip()
            if value.startswith("["):
                return json.loads(value)
            return [o.strip() for o in value.split(",") if o.strip()]
        return value


settings = Settings()
