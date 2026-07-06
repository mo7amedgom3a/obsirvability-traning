from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    service_name: str = "chaos-service"
    environment: str = "local"

    log_level: str = "INFO"
    json_logs: bool = True

    # Fake external dependency
    weather_api_url: str = "http://localhost:9000"
    weather_api_timeout_seconds: float = 3.0

    # Resource endpoints
    cpu_burn_max_seconds: int = 30
    memory_leak_max_mb_per_call: int = 200

    # Fake DB
    slow_db_probability: float = 0.2
    slow_db_sleep_seconds: float = 4.0


settings = Settings()
