"""GeoCLIP coordinate predictor — the GeoSpy-style core.

GeoCLIP (Vivanco et al., NeurIPS 2023) predicts *real GPS coordinates* for an
image, returning a ranked gallery of (lat, lon) with probabilities. It is the
closest openly-available model to commercial tools such as GeoSpy: instead of
only naming a country, it places the photo on the map.

It is OPTIONAL. If the `geoclip` package or its weights cannot be loaded, the
engine marks itself failed and callers transparently fall back to StreetCLIP
country inference. Heavy imports (torch, geoclip) happen only inside load(),
so importing this module never pulls in those dependencies.
"""
from __future__ import annotations

import logging
import os
import tempfile
import threading
from typing import Optional

from PIL import Image

from ..config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


class GeoEngine:
    def __init__(self) -> None:
        self._model = None
        self._device = "cpu"
        self._lock = threading.Lock()
        self._failed = False
        self._name = "GeoCLIP"

    @property
    def name(self) -> str:
        return self._name

    @property
    def available(self) -> bool:
        """True until a load attempt has definitively failed."""
        return settings.enable_geoclip and not self._failed

    def load(self) -> None:
        if self._model is not None or self._failed or not settings.enable_geoclip:
            return
        with self._lock:
            if self._model is not None or self._failed:
                return
            try:
                import torch
                from geoclip import GeoCLIP

                if settings.device == "auto":
                    self._device = "cuda" if torch.cuda.is_available() else "cpu"
                else:
                    self._device = settings.device
                logger.info("Loading GeoCLIP on %s ...", self._device)
                self._model = GeoCLIP().to(self._device)
                logger.info("GeoCLIP ready.")
            except Exception as exc:  # package missing, no weights, OOM, ...
                logger.warning(
                    "GeoCLIP unavailable (%s) — falling back to StreetCLIP country inference.",
                    exc,
                )
                self._failed = True

    def predict(self, image: Image.Image, top_k: Optional[int] = None) -> list[tuple[float, float, float]]:
        """Return [(lat, lon, prob), ...] best-first. Empty list if unavailable.

        geoclip's API reads from a file path, so the image is written to a short
        lived temp JPEG (this also normalises HEIC/PNG inputs uniformly).
        """
        self.load()
        if self._model is None:
            return []
        top_k = top_k or settings.geoclip_top_k
        tmp = tempfile.NamedTemporaryFile(suffix=".jpg", delete=False)
        try:
            image.convert("RGB").save(tmp.name, "JPEG", quality=95)
            tmp.close()
            gps, probs = self._model.predict(tmp.name, top_k=top_k)
            out: list[tuple[float, float, float]] = []
            for (lat, lon), p in zip(gps.tolist(), probs.tolist()):
                out.append((float(lat), float(lon), float(p)))
            return out
        except Exception as exc:
            logger.warning("GeoCLIP prediction failed: %s", exc)
            return []
        finally:
            try:
                os.unlink(tmp.name)
            except OSError:
                pass


_geo: Optional[GeoEngine] = None


def get_geo_engine() -> GeoEngine:
    global _geo
    if _geo is None:
        _geo = GeoEngine()
    return _geo
