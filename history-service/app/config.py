from pydantic_settings import BaseSettings, SettingsConfigDict
from functools import lru_cache


class Settings(BaseSettings):
    postgres_user: str
    postgres_password: str
    postgres_db: str
    postgres_host: str = "localhost"
    postgres_port: int = 5432

    kafka_broker: str
    kafka_topic: str = "wallet_events"
    consumer_group: str = "history-service"
    batch_size: int = 100

    app_name: str = "History Service"
    debug: bool = True

    model_config = SettingsConfigDict(env_file="../.env.local", case_sensitive=False, extra="ignore")


    @property
    def database_url(self) -> str:
        return (
            f"postgresql://{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )
    

@lru_cache
def get_settings() -> Settings:
    return Settings()

print(get_settings())