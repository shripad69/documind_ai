import os
from pathlib import Path


class Settings:
    database_url: str = os.getenv(
        "DATABASE_URL",
        "postgresql+psycopg://rag:local-dev-password@db:5432/document_chatbot",
    )
    redis_url: str = os.getenv("REDIS_URL", "redis://redis:6379/0")
    jwt_secret_key: str = os.getenv("JWT_SECRET_KEY", "local-development-secret-change-before-deploy")
    jwt_algorithm: str = "HS256"
    access_token_hours: int = int(os.getenv("ACCESS_TOKEN_HOURS", "12"))
    upload_dir: Path = Path(os.getenv("UPLOAD_DIR", "/app/storage"))
    max_upload_bytes: int = int(os.getenv("MAX_UPLOAD_BYTES", str(25 * 1024 * 1024)))
    frontend_origin: str = os.getenv("FRONTEND_ORIGIN", "http://localhost:8080")
    cookie_secure: bool = os.getenv("COOKIE_SECURE", "false").lower() == "true"
    gemini_api_key: str | None = os.getenv("GOOGLE_API_KEY")
    openrouter_api_key: str | None = os.getenv("OPENROUTER_API_KEY")
    openrouter_model: str = os.getenv("OPENROUTER_MODEL", "google/gemma-4-31b-it:free")
    openrouter_fallback_models: tuple[str, ...] = tuple(
        model.strip()
        for model in os.getenv(
            "OPENROUTER_FALLBACK_MODELS",
            "nvidia/nemotron-3.5-lightning:free,nvidia/nemotron-3-ultra-550b-a55b:free",
        ).split(",")
        if model.strip()
    )
    openrouter_base_url: str = os.getenv("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1")
    openrouter_timeout_seconds: float = float(os.getenv("OPENROUTER_TIMEOUT_SECONDS", "90"))


settings = Settings()
