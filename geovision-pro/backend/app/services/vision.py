"""Vision engine: CLIP / StreetCLIP zero-shot geolocation + scene analysis.

This is the honest core. StreetCLIP gives strong COUNTRY / REGION level signals.
It does NOT pinpoint streets or buildings — that is a research limitation, not a bug.
The engine exposes:
  * zero_shot(image, labels, template) -> ranked (label, score)
  * embed_image(image) -> L2-normalized numpy vector (for reference similarity)
"""
from __future__ import annotations

import logging
import threading
from typing import Optional

import numpy as np
from PIL import Image

from ..config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


class VisionEngine:
    def __init__(self) -> None:
        self._model = None
        self._processor = None
        self._device = "cpu"
        self._model_name = ""
        self._text_cache: dict[tuple, "np.ndarray"] = {}
        self._logit_scale = 100.0
        self._lock = threading.Lock()

    # ---- lifecycle -------------------------------------------------------
    @property
    def model_name(self) -> str:
        return self._model_name

    @property
    def loaded(self) -> bool:
        return self._model is not None

    def load(self) -> None:
        if self._model is not None:
            return
        with self._lock:
            if self._model is not None:
                return
            import torch
            from transformers import CLIPModel, CLIPProcessor

            # Use all available CPU cores for inference (big win on CPU Spaces).
            try:
                import os
                torch.set_num_threads(max(1, os.cpu_count() or 1))
            except Exception:
                pass

            if settings.device == "auto":
                self._device = "cuda" if torch.cuda.is_available() else "cpu"
            else:
                self._device = settings.device

            for name in (settings.vision_model, settings.vision_fallback_model):
                try:
                    logger.info("Loading vision model %s on %s ...", name, self._device)
                    self._model = CLIPModel.from_pretrained(name).to(self._device).eval()
                    self._processor = CLIPProcessor.from_pretrained(name)
                    self._model_name = name
                    self._logit_scale = float(self._model.logit_scale.exp().item())
                    logger.info("Vision model ready: %s", name)
                    return
                except Exception as exc:  # try fallback
                    logger.warning("Failed to load %s: %s", name, exc)
                    self._model = None
            raise RuntimeError("No vision model could be loaded (check network / disk / model name).")

    # ---- inference -------------------------------------------------------
    def _encode_text(self, labels: tuple[str, ...], template: str) -> "np.ndarray":
        key = (self._model_name, template, labels)
        cached = self._text_cache.get(key)
        if cached is not None:
            return cached
        import torch

        prompts = [template.format(lbl) for lbl in labels]
        inputs = self._processor(text=prompts, return_tensors="pt", padding=True).to(self._device)
        with torch.no_grad():
            feats = self._model.get_text_features(**inputs)
        feats = feats / feats.norm(p=2, dim=-1, keepdim=True)
        arr = feats.cpu().numpy().astype("float32")
        self._text_cache[key] = arr
        return arr

    def embed_image(self, image: Image.Image) -> "np.ndarray":
        self.load()
        import torch

        inputs = self._processor(images=image, return_tensors="pt").to(self._device)
        with torch.no_grad():
            feats = self._model.get_image_features(**inputs)
        feats = feats / feats.norm(p=2, dim=-1, keepdim=True)
        return feats.cpu().numpy().astype("float32")[0]

    def classify(
        self,
        img_vec: "np.ndarray",
        labels: list[str],
        template: str = "a photo of {}",
        top_k: Optional[int] = None,
    ) -> list[tuple[str, float]]:
        """Rank labels for an *already-encoded* image vector (no image encode).

        Encoding the image is by far the most expensive step on CPU, so callers
        should embed once and reuse the vector across all label groups.
        """
        self.load()
        txt = self._encode_text(tuple(labels), template)  # (N, D), cached
        logits = (txt @ img_vec) * self._logit_scale  # (N,)
        logits = logits - logits.max()
        probs = np.exp(logits)
        probs = probs / probs.sum()
        ranked = sorted(zip(labels, probs.tolist()), key=lambda x: x[1], reverse=True)
        return ranked[:top_k] if top_k else ranked

    def zero_shot(
        self,
        image: Image.Image,
        labels: list[str],
        template: str = "a photo of {}",
        top_k: Optional[int] = None,
    ) -> list[tuple[str, float]]:
        """Convenience: encode `image` then classify. Prefer classify() when the
        same image is scored against several label groups."""
        return self.classify(self.embed_image(image), labels, template, top_k)


_engine: Optional[VisionEngine] = None


def get_engine() -> VisionEngine:
    global _engine
    if _engine is None:
        _engine = VisionEngine()
        if not settings.model_lazy_load:
            _engine.load()
    return _engine
