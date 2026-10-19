"""Local naming. Propose, bind, or abstain. Never downloads.

A hint list is a set of proposals, not the world. A contrastive score has to
beat an unnamed prompt before a word is allowed onto the chip. Proper names
are split off later and are not enrolled.
"""

from __future__ import annotations

import importlib.util
import os
from pathlib import Path

from semblon.visual.model import HINTS

_ABSTAIN = "a piece of a photograph with no specific name"
_FAIL: dict[str, str | None] = {"weights": None, "error": None}
_MODEL = {"key": None, "bundle": None}


def siglip_weights_path() -> Path | None:
    """Local file or directory only. Never downloads."""
    env = os.environ.get("SEMBLON_SIGLIP_WEIGHTS", "").strip()
    if env:
        path = Path(env)
        if path.is_file() or (path.is_dir() and any(path.iterdir())):
            return path
        return None
    root = Path.home() / ".cache" / "semblon" / "siglip"
    if not root.exists():
        return None
    if root.is_file():
        return root
    files = sorted(root.glob("*.pt")) + sorted(root.glob("*.bin")) + sorted(root.glob("*.safetensors"))
    if files:
        return files[0]
    if any(root.iterdir()):
        return root
    return None


def _runtime_present() -> str | None:
    if importlib.util.find_spec("open_clip") is not None:
        return "open_clip"
    if importlib.util.find_spec("transformers") is not None:
        return "transformers"
    return None


def siglip_capability() -> dict:
    runtime = _runtime_present()
    weights = siglip_weights_path()
    if runtime is None:
        return {"state": "UNAVAILABLE", "note": "no local contrastive runtime (open_clip or transformers)"}
    if weights is None:
        return {
            "state": "UNAVAILABLE",
            "note": "no local naming weights (SEMBLON_SIGLIP_WEIGHTS or ~/.cache/semblon/siglip)",
        }
    if _FAIL.get("error") and _FAIL.get("weights") == str(weights):
        return {"state": "FAILED", "note": _FAIL["error"], "weights": str(weights), "runtime": runtime}
    return {
        "state": "READY",
        "note": f"local checkpoint {weights.name}; a word still has to beat abstain",
        "weights": str(weights),
        "runtime": runtime,
    }


def mark_naming_failed(weights: str, message: str) -> None:
    _FAIL["weights"] = weights
    _FAIL["error"] = message
    _MODEL["key"] = None
    _MODEL["bundle"] = None


def proposal_nouns() -> list[str]:
    """Hints, plus an optional owner file. Neither list is the universe."""
    found: list[str] = []
    env = os.environ.get("SEMBLON_NOUNS", "").strip()
    if env:
        path = Path(env)
        if path.is_file():
            for line in path.read_text(encoding="utf-8").splitlines():
                text = line.strip()
                if text and not text.startswith("#"):
                    found.append(text)
    for hint in sorted(HINTS):
        if hint not in found:
            found.append(hint)
    return found


def gated_similarity(best: float, abstain: float, *, margin: float = 0.02) -> float:
    """Drop a noun that does not beat 'no specific name'."""
    if best < abstain + margin:
        return 0.0
    return max(0.0, float(best))


class PreparedNaming:
    def __init__(self, cap: dict):
        self.cap = cap

    @property
    def available(self) -> bool:
        return self.cap.get("state") == "READY"

    def status(self) -> dict:
        return dict(self.cap)

    def scorer(self, rgb, masks):
        weights = self.cap.get("weights") or ""
        try:
            bundle = _load_bundle(weights, self.cap.get("runtime"))
        except Exception as exc:  # noqa: BLE001 — naming must not take Home down
            message = f"{type(exc).__name__}: {exc}"
            mark_naming_failed(str(weights), message)
            self.cap = siglip_capability()
            raise
        session = _Session(rgb, masks, bundle)
        self.cap = {**self.cap, "note": "loaded; abstain still wins a weak match"}
        return proposal_nouns(), session.score


def prepare_naming() -> PreparedNaming:
    return PreparedNaming(siglip_capability())


def name_crop_detail(bgr) -> tuple[str | None, float | None]:
    """Noun plus the score that beat abstain. None when the model is absent or abstains."""
    cap = siglip_capability()
    if cap.get("state") != "READY":
        return None, None
    weights = str(cap.get("weights") or "")
    try:
        bundle = _load_bundle(weights, cap.get("runtime"))
        noun, score = _best_noun(bgr, bundle)
    except Exception as exc:  # noqa: BLE001 — a naming failure stays unlabelled
        mark_naming_failed(weights, f"{type(exc).__name__}: {exc}")
        return None, None
    if not noun or score <= 0:
        return None, None
    return f"Looks like a {noun}.", float(score)


def name_crop_bgr(bgr) -> str | None:
    """One grounded noun for this crop, or None when the model abstains or is absent.

    The noun has to beat "no specific name". A missing weight file stays silent.
    This does not write a person and does not decide which archive photos match.
    """
    text, _score = name_crop_detail(bgr)
    return text


def _best_noun(bgr, bundle) -> tuple[str | None, float]:
    import numpy as np
    from PIL import Image

    arr = np.asarray(bgr)
    if arr.ndim != 3 or arr.shape[2] < 3 or arr.shape[0] < 1 or arr.shape[1] < 1:
        return None, 0.0
    rgb = arr[:, :, :3][:, :, ::-1]
    image = Image.fromarray(np.ascontiguousarray(rgb.astype(np.uint8)), "RGB")
    session = _CropNouns(image, bundle)
    best_noun = None
    best = -1.0
    for noun in proposal_nouns():
        score = session.cosine(f"a photo of a {noun}")
        if score > best:
            best = score
            best_noun = noun
    if best_noun is None:
        return None, 0.0
    abstain = session.cosine(_ABSTAIN)
    return best_noun, gated_similarity(best, abstain)


class _CropNouns:
    def __init__(self, image, bundle):
        self.image = image
        self.bundle = bundle
        self._image_feat = None
        self._text: dict[str, object] = {}

    def cosine(self, prompt: str) -> float:
        torch = self.bundle["torch"]
        value = (self.image_feat() * self._text_feat(prompt)).sum(dim=-1)
        return float(value.detach().flatten()[0].item()) if torch.is_tensor(value) else float(value)

    def image_feat(self):
        if self._image_feat is not None:
            return self._image_feat
        torch = self.bundle["torch"]
        kind = self.bundle["kind"]
        with torch.no_grad():
            if kind == "open_clip":
                tensor = self.bundle["preprocess"](self.image).unsqueeze(0)
                feat = self.bundle["model"].encode_image(tensor)
            else:
                inputs = self.bundle["processor"](images=self.image, return_tensors="pt")
                feat = self.bundle["model"].get_image_features(**inputs)
            feat = feat / feat.norm(dim=-1, keepdim=True).clamp(min=1e-6)
        self._image_feat = feat
        return feat

    def _text_feat(self, prompt: str):
        cached = self._text.get(prompt)
        if cached is not None:
            return cached
        torch = self.bundle["torch"]
        kind = self.bundle["kind"]
        with torch.no_grad():
            if kind == "open_clip":
                tokens = self.bundle["tokenizer"]([prompt])
                feat = self.bundle["model"].encode_text(tokens)
            else:
                inputs = self.bundle["processor"](text=[prompt], return_tensors="pt", padding=True)
                feat = self.bundle["model"].get_text_features(**inputs)
            feat = feat / feat.norm(dim=-1, keepdim=True).clamp(min=1e-6)
        self._text[prompt] = feat
        return feat


def _load_bundle(weights: str, runtime: str | None):
    key = (weights, runtime)
    if _MODEL["key"] == key and _MODEL["bundle"] is not None:
        return _MODEL["bundle"]
    path = Path(weights)
    bundle = None
    if runtime == "transformers" and path.is_dir():
        bundle = _load_transformers(path)
    elif runtime == "open_clip":
        bundle = _load_open_clip(path)
    elif runtime == "transformers":
        bundle = _load_transformers(path)
    if bundle is None:
        raise RuntimeError(f"could not load naming weights at {weights}")
    _MODEL["key"] = key
    _MODEL["bundle"] = bundle
    return bundle


def _load_open_clip(path: Path):
    import open_clip
    import torch

    name = "ViT-B-32"
    lowered = path.name.lower()
    if "siglip" in lowered and "so400m" in lowered:
        name = "ViT-SO400M-14-SigLIP-384"
    elif "siglip" in lowered and "384" in lowered:
        name = "ViT-L-16-SigLIP-384"
    elif "siglip" in lowered:
        name = "ViT-B-16-SigLIP"
    pretrained = str(path) if path.is_file() else str(path)
    model, _, preprocess = open_clip.create_model_and_transforms(name, pretrained=pretrained)
    model.eval()
    tokenizer = open_clip.get_tokenizer(name)
    return {"kind": "open_clip", "model": model, "preprocess": preprocess, "tokenizer": tokenizer, "torch": torch}


def _load_transformers(path: Path):
    import torch
    from transformers import AutoModel, AutoProcessor

    model = AutoModel.from_pretrained(str(path), local_files_only=True)
    processor = AutoProcessor.from_pretrained(str(path), local_files_only=True)
    model.eval()
    return {"kind": "transformers", "model": model, "processor": processor, "torch": torch}


class _Session:
    def __init__(self, rgb, masks, bundle):
        self.rgb = rgb
        self.masks = masks
        self.bundle = bundle
        self._crop_feat: dict[int, object] = {}
        self._text: dict[str, object] = {}
        self._abstain = self._text_feat(_ABSTAIN)

    def score(self, region, noun, parent=None, context=None) -> float:
        feat = self._crop_feat_for(region)
        prompts = [f"a photo of a {noun}"]
        parent_label = getattr(parent, "label", None) if parent is not None else None
        if parent_label:
            prompts.append(f"a {noun} that is part of a {parent_label}")
        if context:
            neighbour = context[0]
            if neighbour and neighbour != noun:
                prompts.append(f"a {noun} near {neighbour}")
        best = max(self._cos(feat, self._text_feat(prompt)) for prompt in prompts)
        abstain = self._cos(feat, self._abstain)
        return gated_similarity(best, abstain)

    def _crop_feat_for(self, region):
        rid = int(region.region_id)
        if rid in self._crop_feat:
            return self._crop_feat[rid]
        import numpy as np
        from PIL import Image

        x, y, w, h = region.bbox
        crop = np.asarray(self.rgb[y : y + h, x : x + w]).copy()
        mask = self.masks.get(rid)
        if mask is not None:
            piece = np.asarray(mask[y : y + h, x : x + w])
            if piece.shape[:2] == crop.shape[:2]:
                crop[~piece] = 127
        image = Image.fromarray(crop.astype(np.uint8), "RGB")
        feat = self._image_feat(image)
        self._crop_feat[rid] = feat
        return feat

    def _image_feat(self, image):
        torch = self.bundle["torch"]
        kind = self.bundle["kind"]
        with torch.no_grad():
            if kind == "open_clip":
                tensor = self.bundle["preprocess"](image).unsqueeze(0)
                feat = self.bundle["model"].encode_image(tensor)
                feat = feat / feat.norm(dim=-1, keepdim=True).clamp(min=1e-6)
                return feat
            inputs = self.bundle["processor"](images=image, return_tensors="pt")
            feat = self.bundle["model"].get_image_features(**inputs)
            feat = feat / feat.norm(dim=-1, keepdim=True).clamp(min=1e-6)
            return feat

    def _text_feat(self, prompt: str):
        cached = self._text.get(prompt)
        if cached is not None:
            return cached
        torch = self.bundle["torch"]
        kind = self.bundle["kind"]
        with torch.no_grad():
            if kind == "open_clip":
                tokens = self.bundle["tokenizer"]([prompt])
                feat = self.bundle["model"].encode_text(tokens)
            else:
                inputs = self.bundle["processor"](text=[prompt], return_tensors="pt", padding=True)
                feat = self.bundle["model"].get_text_features(**inputs)
            feat = feat / feat.norm(dim=-1, keepdim=True).clamp(min=1e-6)
        self._text[prompt] = feat
        return feat

    def _cos(self, image_feat, text_feat) -> float:
        torch = self.bundle["torch"]
        value = (image_feat * text_feat).sum(dim=-1)
        return float(value.detach().flatten()[0].item()) if torch.is_tensor(value) else float(value)
