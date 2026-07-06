"""
Central configuration for the ETL platform.

All settings are sourced from environment variables so the same code
runs unmodified across local dev, AWS Glue, and CI. See .env.example
for the full list of supported variables.
"""
import os
from dataclasses import dataclass


def _env(name: str, default: str = None, required: bool = False) -> str:
    value = os.environ.get(name, default)
    if required and value is None:
        raise EnvironmentError(f"Required environment variable '{name}' is not set")
    return value


@dataclass(frozen=True)
class DatabaseConfig:
    host: str = _env("AURORA_HOST", "localhost")
    port: int = int(_env("AURORA_PORT", "5432"))
    database: str = _env("AURORA_DB", "fab_ops")
    user: str = _env("AURORA_USER", "postgres")
    password: str = _env("AURORA_PASSWORD", "postgres")
    schema: str = _env("AURORA_METADATA_SCHEMA", "metadata")
    sslmode: str = _env("AURORA_SSLMODE", "prefer")

    @property
    def sqlalchemy_url(self) -> str:
        return (
            f"postgresql+psycopg2://{self.user}:{self.password}"
            f"@{self.host}:{self.port}/{self.database}?sslmode={self.sslmode}"
        )


@dataclass(frozen=True)
class S3Config:
    region: str = _env("AWS_REGION", "us-east-1")
    endpoint_url: str = _env("S3_ENDPOINT_URL", None)  # set for LocalStack / MinIO in dev


@dataclass(frozen=True)
class AgentConfig:
    provider: str = _env("AGENT_MODEL_PROVIDER", "anthropic")
    model: str = _env("AGENT_MODEL_NAME", "claude-sonnet-5")
    enabled: bool = _env("AGENTS_ENABLED", "true").lower() == "true"
    api_key: str = _env("ANTHROPIC_API_KEY", None)


@dataclass(frozen=True)
class PipelineConfig:
    max_batch_retries: int = int(_env("MAX_BATCH_RETRIES", "3"))
    self_healing_enabled: bool = _env("SELF_HEALING_ENABLED", "true").lower() == "true"
    log_level: str = _env("LOG_LEVEL", "INFO")


DB = DatabaseConfig()
S3 = S3Config()
AGENTS = AgentConfig()
PIPELINE = PipelineConfig()
