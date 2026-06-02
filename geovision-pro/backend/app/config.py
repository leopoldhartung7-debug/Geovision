"""Application configuration loaded from environment variables."""
from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_prefix="GEOVISION_", extra="ignore")

    # General
    app_name: str = "GeoVision Pro API"
    debug: bool = False
    cors_origins: str = "*"  # comma separated

    # Database
    database_url: str = "postgresql+asyncpg://geovision:geovision@localhost:5432/geovision"

    # Vision model
    # StreetCLIP is purpose-built for geolocation but large (~600MB).
    # Fallback to a small CLIP keeps the service runnable on modest hardware.
    vision_model: str = "geolocal/StreetCLIP"
    vision_fallback_model: str = "openai/clip-vit-base-patch32"
    device: str = "auto"  # "auto" | "cpu" | "cuda"
    model_lazy_load: bool = True

    # GeoCLIP — predicts real GPS coordinates (GeoSpy-style). Optional: if the
    # `geoclip` package/weights are missing, we fall back to StreetCLIP country
    # inference. This is what lifts results from "country guess" to coordinates.
    enable_geoclip: bool = True
    geoclip_top_k: int = 10        # coordinate candidates per view (more = finer clustering)
    geoclip_tta: bool = False      # test-time augmentation (3x slower); off for speed
    geoclip_cluster_km: float = 75.0  # merge predictions within this radius into one cluster

    # External services
    nominatim_url: str = "https://nominatim.openstreetmap.org"
    nominatim_email: str = ""  # set to identify yourself per OSM usage policy
    http_timeout: float = 20.0

    # Optional features
    reference_dir: str = ""        # folder of geotagged reference images for similarity; empty disables
    enable_ocr: bool = True        # requires the `tesseract` binary on the host
    max_video_frames: int = 12     # frames sampled per video
    upload_max_mb: int = 40


@lru_cache
def get_settings() -> Settings:
    return Settings()
