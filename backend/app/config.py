"""Application configuration via environment variables."""

from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict


PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="RUSTDALI_",
        env_file=PROJECT_ROOT / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Database (all from .env, no defaults for secrets)
    db_host: str = "localhost"
    db_port: int = 5432
    db_name: str = "ecod_protein"
    db_user: str = "ecod"
    db_password: str  # required — must be in .env
    db_schema: str = "rustdali"

    @property
    def database_url(self) -> str:
        return (
            f"postgresql://{self.db_user}:{self.db_password}"
            f"@{self.db_host}:{self.db_port}/{self.db_name}"
        )

    # Paths
    data_dir: Path = PROJECT_ROOT / "data"

    @property
    def jobs_dir(self) -> Path:
        return self.data_dir / "jobs"

    @property
    def upload_dir(self) -> Path:
        return self.data_dir / "uploads"

    @property
    def ecod_dat_dir(self) -> Path:
        return self.data_dir / "libraries" / "ecod"

    @property
    def pdb_dat_dir(self) -> Path:
        return self.data_dir / "libraries" / "pdb"

    # SLURM
    slurm_partition: str = "main"
    slurm_account: str = ""
    slurm_cpus_per_task: int = 4
    slurm_mem_gb: int = 8
    slurm_time_limit: str = "4:00:00"

    # Auth
    api_key_header: str = "X-API-Key"

    # Server
    host: str = "0.0.0.0"
    port: int = 8000


settings = Settings()
