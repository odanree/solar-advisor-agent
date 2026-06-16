from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    anthropic_api_key: str = ""
    nrel_api_key: str = ""
    eia_api_key: str = ""
    dsire_base_url: str = "https://programs.dsireusa.org/api/v1"
    solar_cost_graphql_url: str = ""

    langfuse_host: str = ""
    langfuse_public_key: str = ""
    langfuse_secret_key: str = ""

    log_level: str = "INFO"


def get_settings() -> Settings:
    return Settings()
