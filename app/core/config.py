from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # extra="ignore": .env also holds the POSTGRES_* values that only docker-compose uses
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # No defaults: these must be set in .env (or as environment variables)
    database_url: str
    embedding_model: str
    embedding_dimensions: int  # must match the model: 384 for bge-small-en-v1.5
    openai_api_key: str
    openai_model: str


settings = Settings()
