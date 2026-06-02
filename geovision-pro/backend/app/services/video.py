"""Video frame sampling via OpenCV.

Honest scope: we sample evenly spaced, sharp frames and analyse them as images,
then aggregate. We do NOT reconstruct a precise travel route from pixels — that is
not reliably possible. The aggregate location is the consensus of analysed frames.
"""
from __future__ import annotations

import logging
import os
import tempfile

import numpy as np
from PIL import Image

from ..config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


def _sharpness(gray: "np.ndarray") -> float:
    import cv2

    return float(cv2.Laplacian(gray, cv2.CV_64F).var())


def extract_keyframes(data: bytes, max_frames: int | None = None) -> list[Image.Image]:
    """Sample up to `max_frames` evenly spaced, reasonably sharp frames."""
    import cv2

    max_frames = max_frames or settings.max_video_frames
    tmp = tempfile.NamedTemporaryFile(suffix=".mp4", delete=False)
    try:
        tmp.write(data)
        tmp.flush()
        tmp.close()
        cap = cv2.VideoCapture(tmp.name)
        total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT)) or 0
        if total <= 0:
            # Fallback: read sequentially
            frames = []
            ok, frame = cap.read()
            while ok and len(frames) < max_frames:
                frames.append(frame)
                for _ in range(15):
                    ok, frame = cap.read()
            cap.release()
            return [_to_pil(f) for f in frames]

        # Sample 3x candidate positions, keep the sharpest in each bucket.
        positions = np.linspace(0, total - 1, num=min(max_frames * 3, total)).astype(int)
        picked: list[tuple[float, "np.ndarray"]] = []
        for pos in positions:
            cap.set(cv2.CAP_PROP_POS_FRAMES, int(pos))
            ok, frame = cap.read()
            if not ok:
                continue
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            picked.append((_sharpness(gray), frame))
        cap.release()

        picked.sort(key=lambda x: x[0], reverse=True)
        chosen = [f for _, f in picked[:max_frames]]
        return [_to_pil(f) for f in chosen]
    finally:
        try:
            os.unlink(tmp.name)
        except OSError:
            pass


def _to_pil(frame_bgr) -> Image.Image:
    import cv2

    rgb = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)
    return Image.fromarray(rgb)
