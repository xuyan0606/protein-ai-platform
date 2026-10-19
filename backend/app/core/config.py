from __future__ import annotations

from pathlib import Path
from urllib.parse import quote

from pydantic_settings import BaseSettings

BACKEND_ROOT = Path(__file__).resolve().parents[2]
PROJECT_ROOT = BACKEND_ROOT.parent


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

        if not self.DEPLOY_DATA_ROOT:
            default_deploy_root = PROJECT_ROOT / "deploy_data"
            if default_deploy_root.exists():
                self.DEPLOY_DATA_ROOT = str(default_deploy_root)

        def _autodiscover_path(*parts: str) -> str:
            root = (self.DEPLOY_DATA_ROOT or "").strip()
            if not root:
                return ""
            candidate = Path(root).expanduser().joinpath(*parts)
            return str(candidate) if candidate.exists() else ""

        if not self.SIFTS_MAPPING_PATH:
            self.SIFTS_MAPPING_PATH = _autodiscover_path("sifts")
        if not self.FOLDSEEK_DATABASE_ROOT:
            self.FOLDSEEK_DATABASE_ROOT = _autodiscover_path("foldseek")
        if not self.LOCAL_ANNOTATION_FIXTURE_PATH:
            self.LOCAL_ANNOTATION_FIXTURE_PATH = _autodiscover_path("annotations")
        if not self.STRUCTURE_SMOKE_PDB_FILE:
            self.STRUCTURE_SMOKE_PDB_FILE = _autodiscover_path("smoke", "query.pdb")
        if not self.LIPASE_DB_PATH:
            lipase_candidates = []
            deploy_root = (self.DEPLOY_DATA_ROOT or "").strip()
            if deploy_root:
                lipase_candidates.append(Path(deploy_root).expanduser() / "lipase" / "lipase.db")
            lipase_candidates.extend(
                [
                    PROJECT_ROOT / "deploy_data" / "lipase" / "lipase.db",
                    Path("/Users/xuyan/lipase-db/lipase.db"),
                ]
            )
            for candidate in lipase_candidates:
                if candidate.exists():
                    self.LIPASE_DB_PATH = str(candidate)
                    break

        if not self.ENZYME_DB_ROOT:
            enzyme_db_candidates = [
                PROJECT_ROOT.parent / "酶数据库",
                PROJECT_ROOT / "deploy_data" / "enzyme_dbs",
            ]
            for candidate in enzyme_db_candidates:
                if candidate.exists() and candidate.is_dir():
                    self.ENZYME_DB_ROOT = str(candidate)
                    break

        if not self.REDIS_URL:
            auth = ""
            username = self.REDIS_USERNAME.strip()
            password = self.REDIS_PASSWORD.strip()
            if username or password:
                if username:
                    auth = quote(username, safe="")
                    if password:
                        auth += f":{quote(password, safe='')}"
                elif password:
                    auth = f":{quote(password, safe='')}"
                auth += "@"
            self.REDIS_URL = f"redis://{auth}{self.REDIS_HOST}:{self.REDIS_PORT}/{self.REDIS_DB}"

    REDIS_HOST: str = "localhost"
    REDIS_PORT: int = 6379
    REDIS_DB: int = 0
    REDIS_USERNAME: str = ""
    REDIS_PASSWORD: str = ""
    REDIS_URL: str = ""
    SEARCH_CACHE_TTL_SECONDS: int = 60 * 60 * 6
    SEARCH_CACHE_STALE_TTL_SECONDS: int = 60 * 60 * 24

    # ChromaDB
    CHROMA_HOST: str = "localhost"
    CHROMA_PORT: int = 8001

    CORS_ORIGINS: list[str] = ["http://localhost:3000", "http://localhost:5173"]

    # LLM — primary
    LLM_PROVIDER: str = "kuaPao"
    LLM_MODEL: str = "gpt-6-sol"
    OPENAI_API_KEY: str = ""
    OPENAI_BASE_URL: str = ""

    # LLM — fallback
    LLM_FALLBACK_PROVIDER: str = "deepseek"
    LLM_FALLBACK_MODEL: str = "deepseek-v4-pro"
    LLM_DISABLED_PROVIDERS: str = "dashscope"
    LLM_MAX_TOKENS: int = 8192
    LLM_TEMPERATURE: float = 0.7
    LLM_REQUEST_TIMEOUT: int = 120  # seconds per LLM request

    # Anthropic
    ANTHROPIC_API_KEY: str = ""

    # DeepSeek
    DEEPSEEK_API_KEY: str = ""
    DEEPSEEK_MODEL: str = "deepseek-v4-pro"
    DEEPSEEK_V4RO_MODEL: str = "DeepSeek-v4ro"

    # KuaPao (OpenAI-compatible relay)
    KUAPAO_API_KEY: str = ""
    KUAPAO_BASE_URL: str = "https://kuaipao.pro/v1"
    KUAPAO_MODEL: str = "gpt-5.5"
    KUAPAO_GPT56_MODEL: str = "gpt-5.6-terra"
    KUAPAO_SOL_MODEL: str = "gpt-5.6-sol"
    KUAPAO_GPT6_SOL_MODEL: str = "gpt-6-sol"

    # MiniMax-M2.7 (OpenAI-compatible relay)
    MINIMAX_API_KEY: str = ""
    MINIMAX_BASE_URL: str = ""
    MINIMAX_MODEL: str = "MiniMax-M2.7"

    # DashScope / Qwen (阿里云百炼 OpenAI-compatible)
    DASHSCOPE_API_KEY: str = ""
    DASHSCOPE_BASE_URL: str = "https://dashscope.aliyuncs.com/compatible-mode/v1"
    DASHSCOPE_MODEL: str = "qwen3.7-max"

    # Rate limiting
    RATE_LIMIT_REQUESTS: int = 60
    RATE_LIMIT_WINDOW_SECONDS: int = 60

    # Storage (MinIO / S3)
    MINIO_ENDPOINT: str = "localhost:9000"
    MINIO_ACCESS_KEY: str = "minioadmin"
    MINIO_SECRET_KEY: str = "minioadmin"
    MINIO_BUCKET: str = "protein-files"
    MINIO_SECURE: bool = False
    MINIO_REGION: str = ""
    STORAGE_LOCAL_PATH: str = "./storage"
    DEPLOY_DATA_ROOT: str = ""
    ENZYME_DB_ROOT: str = ""
    LIPASE_DB_PATH: str = ""
    LOCAL_ANNOTATION_FIXTURE_PATH: str = ""
    STRUCTURE_SMOKE_PDB_FILE: str = ""
    OPS_SLOW_REQUEST_THRESHOLD_SECONDS: float = 2.0
    OPS_ALERT_WEBHOOK_ENABLED: bool = False
    OPS_ALERT_WEBHOOK_URL: str = ""
    OPS_ALERT_WEBHOOK_KIND: str = "webhook"
    OPS_ALERT_WEBHOOK_TIMEOUT_SECONDS: float = 3.0
    OPS_ALERT_WEBHOOK_RETRY_ATTEMPTS: int = 2
    OPS_ALERT_SILENCE_SECONDS: int = 900
    OPS_ALERT_ESCALATE_AFTER_COUNT: int = 3

    # LLM Retry
    LLM_MAX_RETRIES: int = 3
    LLM_RETRY_DELAY_SECONDS: float = 1.0

    # Computational biology external APIs
    NCBI_API_KEY: str = ""
    UNIPROT_BASE_URL: str = "https://rest.uniprot.org"
    INTERPRO_BASE_URL: str = "https://www.ebi.ac.uk/interpro/api"
    ESMFOLD_API_URL: str = "https://api.esmatlas.com"
    DIFFDOCK_API_URL: str = ""
    PROTEINMPNN_API_URL: str = "https://huggingface.co/api"
    FOLDSEEK_API_URL: str = ""
    FOLDSEEK_BINARY: str = ""
    FOLDSEEK_DATABASE_ROOT: str = ""
    FOLDSEEK_DATABASE_PDB: str = ""
    FOLDSEEK_DATABASE_ALPHAFOLD: str = ""
    FOLDSEEK_DATABASE_CUSTOM: str = ""
    SIFTS_MAPPING_PATH: str = ""
    BLAST_API_URL: str = "https://blast.ncbi.nlm.nih.gov/Blast.cgi"
    BLAST_POLL_INTERVAL: float = 5.0
    BLAST_MAX_POLL_ATTEMPTS: int = 60
    BLAST_POLL_BUDGET_SECONDS: float = 120.0
    BLAST_BACKGROUND_WAIT_SECONDS: int = 1800
    UNIPROT_SEARCH_TIMEOUT_SECONDS: float = 12.0
    BLAST_HTTP_READ_TIMEOUT_SECONDS: float = 60.0

    # Agent strategy governance
    # JSON object override/extension for continuation/new-task/fail-closed policy.
    # Kept empty by default so local defaults remain stable and reviewable.
    AGENT_STRATEGY_POLICY_JSON: str = ""

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8", "extra": "ignore"}


settings = Settings()
