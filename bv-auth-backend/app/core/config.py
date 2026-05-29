import os
from dotenv import load_dotenv
# Charger les variables d'environnement à partir du fichier .env
load_dotenv()

class Settings:
    """Classe de configuration pour l'application FastAPI."""
    SECRET_KEY: str = os.getenv("SECRET_KEY", "")
    ALGORITHM: str = os.getenv("ALGORITHM", "HS256")
    ACCESS_TOKEN_EXPIRE_MINUTES: int = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "30"))
    DATABASE_PATH: str = os.getenv("DATABASE_PATH", "bv_datawarehouse.duckdb")
    FRONTEND_URL: str = os.getenv("FRONTEND_URL", "http://localhost:3000")
    DEFAULT_ADMIN_PASSWORD: str = os.getenv("DEFAULT_ADMIN_PASSWORD", "admin123")
    HOST: str = os.getenv("HOST", "0.0.0.0")
    PORT: int = int(os.getenv("PORT", "8000"))
    JINA_API_KEY: str = os.getenv("JINA_API_KEY", "")
    GROQ_API_KEY: str = os.getenv("API_GROQ", "")
    API_GROQ: str = os.getenv("API_GROQ", "")
    WAREHOUSE_PATH: str = os.getenv("WAREHOUSE_PATH", "bv_datawarehouse.duckdb")
    OPIK_API_KEY: str = os.getenv("OPIK_API_KEY", "")
    OPIK_PROJECT_NAME: str = os.getenv("OPIK_PROJECT_NAME", "bv-multi-agent")
    OPIK_WORKSPACE: str = os.getenv("OPIK_WORKSPACE", "wiem-boujelben")
    OPENAI_API_KEY: str = os.getenv("OPENAI_API_KEY", "")
    # Langfuse tracing (fallback when Opik is unavailable)
    # The Langfuse SDK v4 auto-reads LANGFUSE_SECRET_KEY, LANGFUSE_PUBLIC_KEY,
    # and LANGFUSE_BASE_URL from env. We expose them here for explicit access.
    LANGFUSE_SECRET_KEY: str = os.getenv("LANGFUSE_SECRET_KEY", "")
    LANGFUSE_PUBLIC_KEY: str = os.getenv("LANGFUSE_PUBLIC_KEY", "")
    LANGFUSE_BASE_URL: str = os.getenv("LANGFUSE_BASE_URL", "https://cloud.langfuse.com")
    # "opik" | "langfuse" — switch active tracer without removing the other
    TRACING_BACKEND: str = os.getenv("TRACING_BACKEND", "opik")
    AWS_ACCESS_KEY_ID: str = os.getenv("AWS_ACCESS_KEY_ID", "")
    AWS_SECRET_ACCESS_KEY: str = os.getenv("AWS_SECRET_ACCESS_KEY", "")
    AWS_REGION: str = os.getenv("AWS_REGION", "")
    SES_FROM_EMAIL: str = os.getenv("SES_FROM_EMAIL", "")

settings = Settings()