from pydantic_settings import BaseSettings
from urllib.parse import quote_plus


class Settings(BaseSettings):
    postgres_user: str
    postgres_password: str
    postgres_db: str
    postgres_port: int = 5432
    postgres_host: str = "postgres"
    api_port: int = 8000
    jwt_secret_key: str
    backup_api_key: str
    telegram_bot_token: str
    telegram_chat_id: str
    unifi_api_key: str
    unifi_controller_url: str
    pfsense_host: str
    pfsense_snmp_community: str

    @property
    def database_url(self) -> str:
        encoded_password = quote_plus(self.postgres_password)
        return (
            f"postgresql+asyncpg://{self.postgres_user}:{encoded_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )

    class Config:
        env_file = ".env"


settings = Settings()
