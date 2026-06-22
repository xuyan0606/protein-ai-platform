from __future__ import annotations

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # General
    APP_NAME: str = "Protein AI Platform"
    DEBUG: bool = True
    SECRET_KEY: str = "dev-secret-change-in-production"

    # Auth / JWT
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7
    ALGORITHM: str = "HS256"

    # Database — set DATABASE_URL directly in .env to override, or set USE_SQLITE=true for local dev
    DATABASE_URL: str = ""
    USE_SQLITE: bool = False
    POSTGRES_USER: str = "postgres"
    POSTGRES_PASSWORD: str = "postgres"
    POSTGRES_DB: str = "protein_ai"
    POSTGRES_HOST: str = "localhost"
    POSTGRES_PORT: int = 5432

    def model_post_init(self, __context: object) -> None:
        if not self.DATABASE_URL:
            if self.USE_SQLITE:
                self.DATABASE_URL = "sqlite+aiosqlite:///./protein_ai.db"
            else:
                self.DATABASE_URL = (
                    f"postgresql+asyncpg://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}"
                    f"@{self.POSTGRES_HOST}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"
                )

    REDIS_HOST: str = "localhost"
    REDIS_PORT: int = 6379
    REDIS_DB: int = 0

    @property
    def REDIS_URL(self) -> str:
        return f"redis://{self.REDIS_HOST}:{self.REDIS_PORT}/{self.REDIS_DB}"

    CORS_ORIGINS: list[str] = ["http://localhost:3000", "http://localhost:5173"]

    # LLM — primary
    LLM_PROVIDER: str = "openai"
    LLM_MODEL: str = "gpt-4o"
    OPENAI_API_KEY: str = ""
    OPENAI_BASE_URL: str = ""

    # LLM — fallback
    LLM_FALLBACK_PROVIDER: str = "deepseek"
    LLM_FALLBACK_MODEL: str = "deepseek-chat"
    LLM_MAX_TOKENS: int = 8192
    LLM_TEMPERATURE: float = 0.7

    # Anthropic
    ANTHROPIC_API_KEY: str = ""

    # DeepSeek
    DEEPSEEK_API_KEY: str = ""

    # KuaPao (OpenAI-compatible relay)
    KUAPAO_API_KEY: str = ""
    KUAPAO_BASE_URL: str = "https://kuaipao.ai/v1"
    KUAPAO_MODEL: str = "gpt-5.4"

    # MiniMax-M2.7 (OpenAI-compatible relay)
    MINIMAX_API_KEY: str = ""
    MINIMAX_BASE_URL: str = ""
    MINIMAX_MODEL: str = "MiniMax-M2.7"

    # Rate limiting
    RATE_LIMIT_REQUESTS: int = 60
    RATE_LIMIT_WINDOW_SECONDS: int = 60

    # Storage (MinIO / S3)
    MINIO_ENDPOINT: str = "localhost:9000"
    MINIO_ACCESS_KEY: str = "minioadmin"
    MINIO_SECRET_KEY: str = "minioadmin"
    MINIO_BUCKET: str = "protein-files"
    STORAGE_LOCAL_PATH: str = "./storage"

    # LLM Retry
    LLM_MAX_RETRIES: int = 3
    LLM_RETRY_DELAY_SECONDS: float = 1.0

    # Computational biology external APIs
    NCBI_API_KEY: str = ""
    UNIPROT_BASE_URL: str = "https://rest.uniprot.org"
    ESMFOLD_API_URL: str = "https://api.esmatlas.com"
    DIFFDOCK_API_URL: str = ""
    PROTEINMPNN_API_URL: str = "https://huggingface.co/api"
    BLAST_API_URL: str = "https://blast.ncbi.nlm.nih.gov/Blast.cgi"
    BLAST_POLL_INTERVAL: float = 5.0
    BLAST_MAX_POLL_ATTEMPTS: int = 60

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8", "extra": "ignore"}


settings = Settings()
