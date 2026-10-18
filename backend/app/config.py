from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=("../.env", ".env"), extra="ignore")

    app_env: str = "development"
    log_level: str = "INFO"
    database_url: str = "postgresql+psycopg://postgres:postgres@localhost:5432/sales"
    cors_origins: str = "http://localhost:5173"
    max_upload_mb: int = 20
    insert_chunk_size: int = 1000
    enable_test_clock: bool = True


settings = Settings()