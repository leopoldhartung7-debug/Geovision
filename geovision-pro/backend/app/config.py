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
    geoclip_top_k: int = 5         # number of coordinate candidates to return
    # Accuracy boosters (no training needed, cost a bit more CPU time):
    geoclip_tta: bool = True       # evaluate original + mirrored view, fuse the gallery probabilities
    geoclip_candidate_pool: int = 64  # gallery entries fused before picking the top_k
    geoclip_country_rerank: bool = True  # down-weight GeoCLIP coords whose country contradicts StreetCLIP

    # Picarta — commercial GeoSpy-class API. Closest thing to GeoSpy accuracy
    # (often city/street level). Optional: needs a free API token. If no token
    # is set, the pipeline silently skips it and uses the open models instead.
    # Get a token at https://picarta.ai (free tier available).
    enable_picarta: bool = True
    picarta_api_token: str = ""    # set GEOVISION_PICARTA_API_TOKEN to enable
    picarta_url: str = "https://picarta.ai/classify"
    picarta_top_k: int = 3         # number of coordinate candidates to request

    # External services
    nominatim_url: str = "https://nominatim.openstreetmap.org"
    nominatim_email: str = ""  # set to identify yourself per OSM usage policy
    http_timeout: float = 20.0

    # Optional features
    # Reference gallery: a folder of YOUR OWN geotagged photos. We embed them
    # once (cached on disk) and match new photos against them — real image
    # retrieval, the way commercial tools pinpoint places. The MORE geotagged
    # images you add, the more places it can recognise. This is the honest,
    # free version of "training with more images". Empty path disables it.
    reference_dir: str = ""
    reference_min_similarity: float = 0.86  # cosine threshold to trust a match as a location
    reference_use_top_k: int = 5            # nearest neighbours fused into the estimate
    enable_ocr: bool = True        # requires the `tesseract` binary on the host
    max_video_frames: int = 12     # frames sampled per video
    upload_max_mb: int = 40


@lru_cache
def get_settings() -> Settings:
    return Settings()
