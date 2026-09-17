from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # Postgres
    postgres_user: str
    postgres_password: str
    postgres_db: str
    db_host: str = "postgres"
    db_port: int = 5432

    # Azure Document Intelligence
    azure_doc_intel_endpoint: str = ""
    azure_doc_intel_key: str = ""

    # LLM
    llm_provider: str = "google"
    llm_model: str = "claude-sonnet-4-5"
    anthropic_api_key: str = ""
    openai_api_key: str = ""
    openai_model: str = "gpt-4o"
    google_api_key: str = ""
    gemini_model: str = "gemini-2.5-flash"

    # Correo entrante (IMAP)
    imap_host: str = "imap.gmail.com"
    imap_user: str = ""
    imap_app_password: str = ""
    email_poll_interval_seconds: int = 300

    # Alertas (SMTP)
    smtp_host: str = "smtp.gmail.com"
    smtp_port: int = 587
    smtp_user: str = ""
    smtp_app_password: str = ""
    alert_email_to: str = ""

    # Telegram
    telegram_bot_token: str = ""
    telegram_allowed_chat_id: str = ""
    telegram_poll_interval_seconds: int = 10

    # API
    upload_api_key: str = ""
    uploads_dir: str = "/app/uploads"

    class Config:
        env_file = ".env"


settings = Settings()
