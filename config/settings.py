from pydantic_settings import BaseSettings
from pydantic import Field
from typing import Optional


class Settings(BaseSettings):
    # Database Configuration
    db_host: str = Field(default="localhost", alias="DB_HOST")
    db_port: int = Field(default=3306, alias="DB_PORT")
    db_name: str = Field(default="laravel_database", alias="DB_NAME")
    db_user: str = Field(default="laravel_user", alias="DB_USER")
    db_password: str = Field(default="laravel_password", alias="DB_PASSWORD")
    
    # Laravel API Configuration
    laravel_api_url: str = Field(default="http://localhost:8000/api", alias="LARAVEL_API_URL")
    laravel_api_token: Optional[str] = Field(default=None, alias="LARAVEL_API_TOKEN")
    laravel_api_email: str = Field(default="admin@example.com", alias="LARAVEL_API_EMAIL")
    laravel_api_password: str = Field(default="admin_password", alias="LARAVEL_API_PASSWORD")
    
    # Encryption Key
    encryption_key: str = Field(default="", alias="ENCRYPTION_KEY")
    
    # Capsolver Configuration
    capsolver_api_key: Optional[str] = Field(default=None, alias="CAPSOLVER_API_KEY")
    
    # Browser Automation Settings
    browser_headless: bool = Field(default=False, alias="BROWSER_HEADLESS")
    browser_timeout: int = Field(default=30000, alias="BROWSER_TIMEOUT")
    screenshot_on_error: bool = Field(default=True, alias="SCREENSHOT_ON_ERROR")
    
    # Gmail API Configuration
    gmail_credentials_path: str = Field(default="credentials.json", alias="GMAIL_CREDENTIALS_PATH")
    gmail_token_path: str = Field(default="token.pickle", alias="GMAIL_TOKEN_PATH")
    gmail_otp_timeout: int = Field(default=300, alias="GMAIL_OTP_TIMEOUT")  # 5 minutes default
    gmail_otp_retry_interval: int = Field(default=10, alias="GMAIL_OTP_RETRY_INTERVAL")  # 10 seconds
    
    # Orchestrator Configuration
    orchestrator_max_concurrent_tasks: int = Field(default=3, alias="ORCHESTRATOR_MAX_CONCURRENT_TASKS")
    orchestrator_sync_interval_minutes: int = Field(default=60, alias="ORCHESTRATOR_SYNC_INTERVAL_MINUTES")
    orchestrator_task_timeout: int = Field(default=300, alias="ORCHESTRATOR_TASK_TIMEOUT")
    orchestrator_max_retries: int = Field(default=3, alias="ORCHESTRATOR_MAX_RETRIES")
    orchestrator_retry_delay: int = Field(default=5, alias="ORCHESTRATOR_RETRY_DELAY")
    
    # Application Settings
    app_env: str = Field(default="development", alias="APP_ENV")
    log_level: str = Field(default="INFO", alias="LOG_LEVEL")
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = False
    
    @property
    def database_url(self) -> str:
        return f"mysql+pymysql://{self.db_user}:{self.db_password}@{self.db_host}:{self.db_port}/{self.db_name}"


settings = Settings()
