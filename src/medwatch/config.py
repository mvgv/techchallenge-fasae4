"""Configurações da aplicação e carregamento de YAML."""
from functools import lru_cache
from pathlib import Path

import yaml
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")
    database_url: str = "postgresql+psycopg://medwatch:medwatch@localhost:5432/medwatch"
    redis_url: str = "redis://localhost:6379/0"
    api_base_url: str = "http://localhost:8000"
    config_dir: Path = Path("config")
    models_dir: Path = Path("models")
    vitals_iforest_model: str = "vitals_iforest"   # vitals_iforest_mimic para dados reais
    log_level: str = "INFO"
    storage_backend: str = "local"
    local_storage_dir: Path = Path("data/storage")
    azure_storage_connection_string: str = ""
    azure_storage_container: str = "media"
    use_fake_azure: bool = False
    azure_speech_key: str = ""
    azure_speech_region: str = "brazilsouth"
    speech_language: str = "pt-BR"
    azure_language_key: str = ""
    azure_language_endpoint: str = ""
    language_code: str = "pt"
    yolo_det_weights: str = "models/yolov8n.pt"
    yolo_pose_weights: str = "models/yolov8n-pose.pt"
    video_target_fps: int = 8
    audio_disable_events: bool = False
    sim_speedup: float = 60.0
    sim_patients: int = 5
    sim_scenario: str = "demo"
    alert_min_level: str = "warning"
    alert_cooldown_minutes: int = 15
    alert_escalation_minutes: int = 5
    teams_webhook_url: str = ""
    logic_app_email_url: str = ""
    alert_email_to: str = ""
    dashboard_url: str = "http://localhost:8501"

@lru_cache
def get_settings() -> Settings:
    """Retorna as configurações (cacheadas)."""
    return Settings()

@lru_cache
def load_yaml(name: str) -> dict:
    """Carrega config/<name>.yaml."""
    path = get_settings().config_dir / f"{name}.yaml"
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}
