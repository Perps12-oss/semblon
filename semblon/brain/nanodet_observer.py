"""NanoDetObserver — YES_WRAP around existing detect_objects. No adoption."""

from __future__ import annotations

from typing import Callable

from semblon.brain.observation import Observation, PhotoRef, Region
from semblon.object_pack import KNOWN_SHA256, PROVIDER, WEIGHT_NAME

# First 16 hex of the pinned NanoDet weight digest.
NANODET_PACK_HASH = KNOWN_SHA256[WEIGHT_NAME][:16]


class NanoDetObserver:
    capability_id = "C1"
    provider_name = "existing_nanodet_tags"
    model_pack_hash = NANODET_PACK_HASH

    def __init__(
        self,
        detect_fn: Callable | None = None,
        *,
        pack_hash: str | None = None,
    ) -> None:
        self._detect = detect_fn
        if pack_hash is not None:
            self.model_pack_hash = pack_hash

    def observe(
        self,
        photo: PhotoRef,
        regions: list[Region] | None = None,
    ) -> list[Observation]:
        detect = self._detect
        if detect is None:
            from semblon.object_nanodet import detect_objects

            detect = detect_objects
            image = photo.path
            if image is None:
                raise ValueError("PhotoRef.path required for NanoDetObserver")
            if hasattr(image, "shape"):
                bgr = image
            else:
                import cv2
                import numpy as np

                bgr = cv2.imread(str(image), cv2.IMREAD_COLOR)
                if bgr is None:
                    raise FileNotFoundError(f"unreadable image: {image}")
                bgr = np.asarray(bgr)
            detections = detect(bgr) or []
        else:
            # Injected detect_fn (tests / fixtures) — no disk read, no model load.
            import numpy as np

            detections = detect(np.zeros((8, 8, 3), dtype=np.uint8)) or []
        tags = []
        for det in detections:
            label = det.get("label") or det.get("class") or det.get("name")
            if not label:
                continue
            tags.append(
                {
                    "label": str(label),
                    "score": float(det.get("score") or det.get("confidence") or 0.0),
                    "bbox": det.get("bbox") or det.get("box"),
                    "source": "nanodet",
                }
            )
        if not tags:
            return []
        conf = max(t["score"] for t in tags)
        return [
            Observation(
                photo_id=photo.photo_id,
                capability_id=self.capability_id,
                provider_name=self.provider_name,
                model_pack_hash=self.model_pack_hash,
                payload={"tags": tags, "provider": PROVIDER},
                confidence=conf,
                content_hash=photo.content_hash,
            )
        ]
