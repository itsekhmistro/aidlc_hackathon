from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_ignore_empty=True)

    PROJECT_NAME: str = "Hackathon API"
    API_V1_STR: str = "/api/v1"

    POSTGRES_SERVER: str = "localhost"
    POSTGRES_PORT: int = 5432
    POSTGRES_USER: str = "postgres"
    POSTGRES_PASSWORD: str = "postgres"
    POSTGRES_DB: str = "hackathon"

    @property
    def DATABASE_URL(self) -> str:
        return (
            f"postgresql+psycopg://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}"
            f"@{self.POSTGRES_SERVER}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"
        )

    BACKEND_CORS_ORIGINS: list[str] = ["http://localhost:5173", "http://localhost:3000"]

    SECRET_KEY: str = "changeme-use-a-real-secret-in-production"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24 * 7

    UPLOAD_DIR: str = "/uploads"
    MAX_FILE_SIZE_BYTES: int = 20 * 1024 * 1024   # 20 MB
    MAX_IMAGE_SIZE_BYTES: int = 3 * 1024 * 1024   # 3 MB

    # ── XMPP bridge (TASK-13) ────────────────────────────────────────────────
    # Off by default so an existing deployment that doesn't run Prosody alongside
    # the backend starts cleanly. Docker-compose for Jabber flips this to true.
    XMPP_ENABLED: bool = False
    XMPP_HOST: str = "prosody"
    XMPP_HTTP_PORT: int = 5280
    XMPP_DOMAIN: str = "server-a.local"
    XMPP_ADMIN_TOKEN: str = ""
    XMPP_WEBHOOK_TOKEN: str = ""
    # When False, the webhook handler writes NULL into federation_log.message_preview
    # regardless of what Prosody sent. See specs/13-jabber-design.md §1.3.
    XMPP_LOG_PREVIEWS: bool = True


settings = Settings()
