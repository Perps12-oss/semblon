"""Typed door from the Qt shell to existing application and domain calls.

QML talks to ShellBridge. ShellBridge talks here. This module does not open
a second archive, does not write identity from observers, and does not invent
operations that have no backend symbol.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from semblon.application import Application
from semblon.native_shell.tokens import SHELL_DENSITY_DEFAULT, cell_size
from semblon.ui_prefs import (
    GRID_DENSITIES,
    KEY_GRID_DENSITY,
    LIBRARY_FILTERS,
    SEARCH_MODES,
    load_prefs,
    load_prefer_gpu,
    save_grid_density,
    save_library_filter,
    save_prefer_gpu,
    save_search_mode,
)


class AdapterError(Exception):
    """Typed failure. ``state`` is error or unavailable."""

    def __init__(self, code: str, message: str, *, state: str = "error") -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.state = state


@dataclass(frozen=True)
class Result:
    state: str
    message: str
    data: dict = field(default_factory=dict)


def _lines(value) -> list[str]:
    if isinstance(value, str):
        return [line.strip() for line in value.splitlines() if line.strip()]
    if isinstance(value, (list, tuple)):
        return [str(line).strip() for line in value if str(line).strip()]
    return []


class ArchiveAdapter:
    def __init__(self, app: Application) -> None:
        self._app = app

    @property
    def store(self) -> Path:
        return Path(self._app.store)

    def archive_summary(self) -> Result:
        count = int(self._app.archive_count())
        if count <= 0:
            return Result("empty", "Your archive is empty.", {"count": 0})
        return Result("ready", f"Showing {count} stills.", {"count": count})

    def browse(self, facet: str) -> Result:
        from semblon.library_browse import folder_buckets, moment_buckets, timeline_buckets

        key = str(facet or "").strip().lower()
        if key == "timeline":
            buckets = timeline_buckets(self.store)
            label = "Days"
        elif key == "folders":
            buckets = folder_buckets(self.store)
            label = "Folders"
        elif key == "moments":
            buckets = moment_buckets(self.store)
            label = "Moments"
        else:
            raise AdapterError("browse.UNKNOWN", f"Unknown browse facet {facet}.")
        slim = [
            {
                "key": str(row.get("key") or ""),
                "label": str(row.get("label") or ""),
                "count": int(row.get("count") or 0),
                "media_ids": [str(mid) for mid in (row.get("media_ids") or []) if mid],
            }
            for row in buckets
        ]
        if not slim:
            return Result("empty", f"{label}: nothing to group yet.", {"facet": key, "buckets": []})
        return Result("ready", f"{label}: {len(slim)} groups.", {"facet": key, "buckets": slim})

    def search(
        self,
        mode: str,
        query: str,
        *,
        within_media_ids: list[str] | None = None,
    ) -> Result:
        key = str(mode or "people").strip().lower()
        text = str(query or "").strip()
        if key not in SEARCH_MODES:
            raise AdapterError("search.UNKNOWN", f"Unknown search mode {mode}.")
        if not text:
            return Result("empty", "Nothing was searched.", {"mode": key, "items": []})
        if key == "people":
            return self._search_people(text)
        if key == "text":
            return self._search_text(text, within_media_ids=within_media_ids)
        if key == "object":
            return self._search_object(text, within_media_ids=within_media_ids)
        if key == "whole":
            return Result(
                "unavailable",
                "Similar: open a photo, then use Similar.",
                {"mode": key},
            )
        return Result(
            "unavailable",
            "Similar: draw a region on the open photo.",
            {"mode": key},
        )

    def _search_people(self, query: str) -> Result:
        from semblon.search import SearchError, search_person

        try:
            rec = search_person(self.store, query)
        except SearchError as exc:
            raise AdapterError("search.PEOPLE", str(exc)) from exc
        names = [str(item.get("display_name") or "").strip() for item in rec.get("items") or []]
        names = [name for name in names if name]
        if not names:
            return Result("empty", "No people matched that search.", {"mode": "people", "names": []})
        preview = ", ".join(names[:3])
        if len(names) <= 3:
            message = f"Found: {preview}."
        else:
            message = f"Found {len(names)} matches. Top results: {preview}."
        return Result("ready", message, {"mode": "people", "names": names, "count": len(names)})

    def _search_text(
        self, query: str, *, within_media_ids: list[str] | None = None
    ) -> Result:
        from semblon.search import SearchError, search_text

        try:
            rec = search_text(self.store, query, within_media_ids=within_media_ids)
        except SearchError as exc:
            raise AdapterError("search.TEXT", str(exc)) from exc
        status = str(rec.get("status") or "")
        basis = str(rec.get("similarity_basis") or "Text in photos (OCR substring)")
        media_ids = [str(m) for m in (rec.get("media_ids") or []) if m]
        if status == "UNAVAILABLE":
            reason = str(rec.get("reason") or "Text in photos is not available yet.")
            return Result(
                "unavailable",
                f"Text search: {reason}",
                {
                    "mode": "text",
                    "media_ids": [],
                    "basis": "text",
                    "basis_label": basis,
                    "note": "Text in photos — not a person.",
                },
            )
        items = list(rec.get("items") or [])
        if status == "NO_RESULT" or not items:
            return Result(
                "empty",
                "Text search: nothing matched.",
                {
                    "mode": "text",
                    "count": 0,
                    "media_ids": [],
                    "basis": "text",
                    "basis_label": basis,
                    "note": "Text in photos — not a person.",
                },
            )
        return Result(
            "ready",
            f"Text search: {len(media_ids) or len(items)} photos with matching text.",
            {
                "mode": "text",
                "count": len(media_ids) or len(items),
                "items": items[:20],
                "media_ids": media_ids,
                "basis": "text",
                "basis_label": basis,
                "note": "Text in photos — not a person.",
            },
        )

    def _search_object(
        self, query: str, *, within_media_ids: list[str] | None = None
    ) -> Result:
        from semblon.search import SearchError, search_object

        try:
            rec = search_object(self.store, query, within_media_ids=within_media_ids)
        except SearchError as exc:
            raise AdapterError("search.OBJECT", str(exc)) from exc
        status = str(rec.get("status") or "")
        basis = str(rec.get("similarity_basis") or "COCO object detection (NanoDet)")
        media_ids = [str(m) for m in (rec.get("media_ids") or []) if m]
        meta = {
            "mode": "object",
            "media_ids": media_ids,
            "basis": "object",
            "basis_label": basis,
            "note": "Object labels are not a person.",
        }
        if status == "UNAVAILABLE":
            reason = str(rec.get("reason") or "Finding things in pictures isn't set up yet.")
            return Result("unavailable", f"Object search: {reason}", {**meta, "media_ids": []})
        items = list(rec.get("items") or [])
        if status == "NO_RESULT" or not items:
            return Result(
                "empty",
                "Object search: nothing matched.",
                {**meta, "count": 0, "media_ids": []},
            )
        return Result(
            "ready",
            f"Object search: {len(media_ids) or len(items)} photos with matching objects.",
            {**meta, "count": len(media_ids) or len(items), "items": items[:20]},
        )

    def similar_media(self, media_id: str, *, search_quality: str | None = None) -> Result:
        from semblon.search import search_similar_media
        from semblon.ui_prefs import load_search_quality

        quality = search_quality or load_search_quality(self.store)
        rec = search_similar_media(self.store, media_id, search_quality=quality)
        return self._similar_result(rec, basis="whole")

    def similar_faces(self, face_id: str) -> Result:
        from semblon.search import search_similar_faces

        rec = search_similar_faces(self.store, face_id)
        return self._similar_result(rec, basis="face")

    def similar_region(self, rec: dict) -> Result:
        """Region door → same Focus strip. Basis comes from the search record."""
        similar = dict((rec or {}).get("similar") or {})
        providers = (rec or {}).get("optional_providers")
        if isinstance(providers, list) and "optional_providers" not in similar:
            similar["optional_providers"] = providers
        if str(similar.get("status") or "") == "UNAVAILABLE":
            reason = str(similar.get("reason") or "")
            lowered = reason.lower()
            if "sqlite" in lowered or "traceback" in lowered or not reason.strip():
                similar["reason"] = "Similar search could not run."
        return self._similar_result(similar, basis="region")

    def _similar_result(self, rec: dict, *, basis: str) -> Result:
        status = str(rec.get("status") or "")
        items = []
        seen: set[str] = set()
        for item in rec.get("items") or []:
            media_id = str(item.get("media_id") or "")
            if not media_id or media_id in seen:
                continue
            seen.add(media_id)
            try:
                score = float(item.get("score") or 0.0)
            except (TypeError, ValueError):
                score = 0.0
            norm = item.get("match_norm") or [0.0, 0.0, 0.0, 0.0]
            if not isinstance(norm, (list, tuple)) or len(norm) != 4:
                norm = [0.0, 0.0, 0.0, 0.0]
            items.append(
                {
                    "media_id": media_id,
                    "score": score,
                    "match_nx": float(norm[0]),
                    "match_ny": float(norm[1]),
                    "match_nw": float(norm[2]),
                    "match_nh": float(norm[3]),
                }
            )
        if basis == "face":
            basis_label = str(rec.get("similarity_basis") or "Same face")
            engine = str(rec.get("engine") or "face-embed")
            empty_msg = f"Similar ({basis_label}): nothing close enough."
            ready_msg = f"Similar ({basis_label}): {len(items)} matches."
        else:
            basis_label = str(rec.get("similarity_basis") or "Colour only")
            engine = str(rec.get("engine") or ("color-hist" if "colour" in basis_label.lower() else "dinov2-vits14"))
            if "colour" in basis_label.lower():
                empty_msg = f"Similar ({basis_label}): no colour histogram matches."
                ready_msg = f"Similar ({basis_label}): {len(items)} colour histogram matches."
            else:
                empty_msg = f"Similar ({basis_label}): nothing close enough."
                noun = "match" if len(items) == 1 else "matches"
                ready_msg = f"Similar ({basis_label}): {len(items)} {noun}."
        from semblon.similarity_profile import resolve_search_quality

        profile = resolve_search_quality(str(rec.get("search_profile") or "balanced"))
        meta = {
            "basis": basis,
            "basis_label": basis_label,
            "engine": engine,
            "items": [],
            "search_profile": str(rec.get("search_profile") or profile.key),
            "search_profile_label": str(rec.get("search_profile_label") or profile.label),
        }
        if rec.get("search_phase"):
            meta["search_phase"] = str(rec.get("search_phase"))
        channels = rec.get("channels")
        if isinstance(channels, list):
            meta["channels"] = channels
        providers = rec.get("optional_providers")
        if isinstance(providers, list):
            meta["optional_providers"] = providers
        if rec.get("error_id"):
            meta["error_id"] = str(rec.get("error_id"))
        if rec.get("understanding"):
            meta["understanding"] = str(rec.get("understanding"))
        strip = str(rec.get("strip_label") or "").strip()
        # Strip label may refine "Same kind", but must never hide Colour only.
        colourish = (
            "colour" in basis_label.lower()
            or "color" in basis_label.lower()
            or "color-hist" in engine.lower()
            or "colour" in strip.lower()
            or "color" in strip.lower()
        )
        if colourish:
            basis_label = "Colour only"
            meta["basis_label"] = basis_label
            engine = str(rec.get("engine") or "color-hist")
            meta["engine"] = engine
            empty_msg = f"Similar ({basis_label}): no colour histogram matches."
            ready_msg = f"Similar ({basis_label}): {len(items)} colour histogram matches."
        elif strip:
            basis_label = strip
            meta["basis_label"] = strip
            if "colour" in strip.lower() or "color" in strip.lower():
                empty_msg = f"Similar ({basis_label}): no colour histogram matches."
                ready_msg = f"Similar ({basis_label}): {len(items)} colour histogram matches."
            else:
                empty_msg = f"Similar ({basis_label}): nothing close enough."
                noun = "match" if len(items) == 1 else "matches"
                ready_msg = f"Similar ({basis_label}): {len(items)} {noun}."
        for key in (
            "query_source",
            "crop_rect",
            "location_uncertain_count",
            "query_pixels",
        ):
            if key in rec:
                meta[key] = rec.get(key)
        if rec.get("error_id") == "region.LOW_INFO":
            meta["low_info"] = True
        spec = rec.get("query_spec")
        if isinstance(spec, dict):
            meta["query_spec"] = spec
        parts = rec.get("parts")
        if isinstance(parts, list):
            meta["parts"] = parts
        if status == "UNAVAILABLE":
            reason = str(rec.get("reason") or "Similar search could not run.").strip()
            if not reason.endswith("."):
                reason += "."
            return Result(
                "unavailable",
                f"Similar ({basis_label}): {reason}",
                {**meta, "items": []},
            )
        if not items:
            if meta.get("low_info"):
                return Result(
                    "empty",
                    f"Similar ({basis_label}): pick a more detailed area.",
                    meta,
                )
            return Result("empty", empty_msg, meta)
        return Result(
            "ready",
            ready_msg,
            {**meta, "items": items[: profile.max_results]},
        )

    def review_counts(self) -> Result:
        try:
            board = self._app.board()
        except Exception as exc:
            text = str(exc).lower()
            if "unknown run" in text or "no run" in text or "store" in text:
                return Result("empty", "Review counts: no reviewed run yet.", {"counts": {}})
            return Result("unavailable", "Review counts: groups could not be read.", {})
        counts = dict(board.get("counts") or {})
        named = int(counts.get("named_persons") or 0)
        review = int(counts.get("review_required") or 0)
        strong = int(counts.get("strong") or 0)
        unassigned = int(counts.get("unassigned") or 0)
        message = (
            f"Review counts: {named} named, {review} need review, "
            f"{strong} strong candidates, {unassigned} unassigned."
        )
        return Result("ready", message, {"counts": counts})

    def unresolved(self, *, include_rejected: bool = False) -> Result:
        try:
            rec = self._app.inbox()
        except Exception as exc:
            text = str(exc).lower()
            if "unknown run" in text or "store not found" in text or "no run" in text:
                return Result("empty", "Unresolved: none yet.", {"counts": {}})
            return Result("unavailable", "Unresolved: could not be read.", {})
        counts = dict(rec.get("counts") or {})
        shown = {
            "UNKNOWN": int(counts.get("UNKNOWN") or 0),
            "REVIEW_REQUIRED": int(counts.get("REVIEW_REQUIRED") or 0),
        }
        if include_rejected:
            shown["REJECTED"] = int(counts.get("REJECTED") or 0)
        faces = []
        for item in rec.get("items") or []:
            bucket = str(item.get("bucket") or "")
            if bucket not in shown:
                continue
            if bucket == "REJECTED" and not include_rejected:
                continue
            faces.append({"face_id": str(item.get("face_id") or ""), "bucket": bucket})
        total = sum(shown.values())
        if total <= 0:
            return Result("empty", "Unresolved: none yet.", {"counts": shown, "faces": []})
        return Result(
            "ready",
            f"Unresolved: {shown['UNKNOWN']} unknown, {shown['REVIEW_REQUIRED']} to review.",
            {"counts": shown, "faces": faces},
        )

    def library_health(self) -> Result:
        from semblon.store import integrity_report

        if not self.store.is_file():
            return Result("empty", "Library check: no library file yet.", {})
        try:
            rec = integrity_report(self.store)
        except FileNotFoundError:
            return Result("empty", "Library check: no library file yet.", {})
        except Exception as exc:
            raise AdapterError("health.FAILED", str(exc)) from exc
        if rec.get("ok"):
            return Result(
                "ready",
                f"Library check: passed. {int(rec.get('media') or 0)} pictures checked.",
                {"report": rec},
            )
        return Result(
            "error",
            "Library check: found a problem. Open Advanced for the detail.",
            {"report": rec},
        )

    def duplicates(self, on_progress=None) -> Result:
        from semblon.duplicates import NEAR_APP_THRESHOLD, find_integrity_groups

        if not self.store.is_file():
            return Result("empty", "Duplicates: no library file yet.", {})
        kwargs: dict = {"near_threshold": NEAR_APP_THRESHOLD}
        if on_progress is not None:
            # The exact pass then the near pass each count from 1, so a drop marks the second pass.
            state = {"phase": 0, "last": 0}

            def _tick(i: int, total: int) -> None:
                if i < state["last"]:
                    state["phase"] = 1
                state["last"] = i
                on_progress(state["phase"], i, total)

            kwargs["on_progress"] = _tick
        rec = find_integrity_groups(self.store, **kwargs)
        exact = int(rec.get("exact_group_count") or 0)
        near = int(rec.get("near_group_count") or 0)
        near_status = str(rec.get("near_status") or "")
        if exact == 0 and near == 0:
            if near_status.upper() in {"UNAVAILABLE", "FAILED"}:
                return Result(
                    "unavailable",
                    "Duplicates: exact scan found none. Near matches need OpenCV.",
                    {"report": rec},
                )
            return Result("empty", "Duplicates: no duplicate candidates were found.", {"report": rec})
        return Result(
            "ready",
            "Duplicates: "
            + ", ".join(
                part for part in (
                    f"{exact} {'set' if exact == 1 else 'sets'} of exact copies" if exact else "",
                    f"{near} {'set' if near == 1 else 'sets'} of near copies" if near else "",
                ) if part
            ) + ".",
            {"report": rec},
        )

    def activity(self) -> Result:
        try:
            rec = self._app.activity_memory()
        except Exception as exc:
            text = str(exc).lower()
            if "unknown run" in text or "no run" in text:
                return Result("empty", "Activity: nothing processed yet.", {})
            return Result("unavailable", "Activity: could not be read.", {})
        if rec.get("empty"):
            return Result("empty", "Activity: nothing processed yet.", {"activity": rec})
        processing = _lines((rec.get("processing") or {}).get("lines"))
        moments = _lines(rec.get("moment_lines"))
        together = _lines(rec.get("together_lines"))
        bits = []
        if processing:
            bits.append(processing[0])
        if together:
            bits.append(together[0])
        if moments:
            bits.append(moments[0])
        detail = " ".join(bits) if bits else "recent processing is on file."
        return Result("ready", f"Activity: {detail}", {"activity": rec})

    def capabilities(self) -> Result:
        from semblon.engine import select_execution_provider
        from semblon.lens import probe_barcode, probe_sam2, probe_siglip, probe_translation, probe_vlm
        from semblon.visual.engine import capabilities

        prefer = load_prefer_gpu(self.store)
        gpu = select_execution_provider(prefer_gpu=True if prefer is None else bool(prefer))
        visual = capabilities()
        probes = {
            "siglip": probe_siglip(),
            "sam2": probe_sam2(),
            "translation": probe_translation(),
            "vlm": probe_vlm(),
            "barcode": probe_barcode(),
            "execution": gpu.get("chosen") or "CPUExecutionProvider",
            "gpu": bool(gpu.get("gpu")),
        }
        missing = [
            name
            for name, state in (
                ("siglip", probes["siglip"]),
                ("sam2", probes["sam2"]),
                ("translation", probes["translation"]),
                ("vlm", probes["vlm"]),
                ("barcode", probes["barcode"]),
            )
            if "READY" not in str(state).upper() and str(state).upper() not in {"AVAILABLE", "OK"}
        ]
        if missing:
            return Result(
                "unavailable",
                "Extras: some extras are not added yet.",
                {"probes": probes, "visual": visual, "missing": missing},
            )
        return Result("ready", "Extras: everything is ready.", {"probes": probes, "visual": visual})

    def gpu_status(self) -> Result:
        from semblon.engine import gpu_product_status, select_execution_provider

        prefer = load_prefer_gpu(self.store)
        effective = True if prefer is None else bool(prefer)
        rec = select_execution_provider(prefer_gpu=effective)
        status = gpu_product_status()
        chosen = str(rec.get("chosen") or "CPUExecutionProvider")
        if rec.get("gpu"):
            message = f"GPU: listed provider {chosen}. Listed is not a proof it will run."
            state = "ready"
        else:
            message = "GPU: no CUDA, DirectML, or TensorRT provider is listed. Work stays on CPU."
            state = "unavailable"
        return Result(state, message, {"execution": rec, "status": status, "prefer": prefer})

    def set_gpu(self, enabled: bool | None) -> Result:
        saved = save_prefer_gpu(enabled, self.store)
        if saved is None:
            return Result("ready", "GPU: preference cleared. Semblon will follow what is listed.", {})
        if saved:
            return Result("ready", "GPU: preference set to try a listed GPU provider on the next add.", {})
        return Result("ready", "GPU: preference set to CPU for the next add.", {})

    def density(self) -> Result:
        raw = str(load_prefs(self.store).get(KEY_GRID_DENSITY) or "").strip().lower()
        key = raw if raw in GRID_DENSITIES else SHELL_DENSITY_DEFAULT
        return Result("ready", f"Density is {key}.", {"density": key, "cell": cell_size(key)})

    def set_density(self, density: str) -> Result:
        key = str(density or "").strip().lower()
        if key not in GRID_DENSITIES:
            raise AdapterError("density.UNKNOWN", f"Unknown density {density}.")
        saved = save_grid_density(key, self.store)
        return Result("ready", f"Density is {saved}.", {"density": saved, "cell": cell_size(saved)})

    def set_search_mode(self, mode: str) -> Result:
        key = str(mode or "").strip().lower()
        if key not in SEARCH_MODES:
            raise AdapterError("search.UNKNOWN", f"Unknown search mode {mode}.")
        saved = save_search_mode(key, self.store)
        label = {
            "people": "named people",
            "text": "text in photos — not a person",
            "object": "objects in photos — not a person",
            "whole": "the whole photo",
            "region": "a region you draw",
        }[saved]
        return Result("ready", f"Search looks at {label}.", {"mode": saved})

    def search_mode(self) -> Result:
        from semblon.ui_prefs import load_search_mode

        key = load_search_mode(self.store)
        labels = {
            "people": "Search looks at named people.",
            "text": "Search looks at text in photos — not a person.",
            "object": "Search looks at objects in photos — not a person.",
            "whole": "Search looks at the whole photo.",
            "region": "Search looks at a region you draw.",
        }
        return Result("ready", labels.get(key, labels["people"]), {"mode": key})

    def set_search_quality(self, value: str) -> Result:
        from semblon.similarity_profile import SEARCH_QUALITIES, search_quality_label
        from semblon.ui_prefs import save_search_quality

        key = str(value or "").strip().lower()
        if key not in SEARCH_QUALITIES:
            raise AdapterError("search.QUALITY", f"Unknown search quality {value}.")
        saved = save_search_quality(key, self.store)
        label = search_quality_label(saved)
        return Result("ready", f"Search quality is {label}.", {"quality": saved, "label": label})

    def search_quality(self) -> Result:
        from semblon.similarity_profile import search_quality_label
        from semblon.ui_prefs import load_search_quality

        key = load_search_quality(self.store)
        label = search_quality_label(key)
        return Result("ready", f"Search quality is {label}.", {"quality": key, "label": label})

    def set_library_filter(self, filter_key: str) -> Result:
        key = str(filter_key or "").strip().lower()
        if key not in LIBRARY_FILTERS:
            raise AdapterError("library.UNKNOWN", f"Unknown library filter {filter_key}.")
        saved = save_library_filter(key, self.store)
        if saved == "videos":
            return Result(
                "unavailable",
                "Showing stills. Video rows are stored apart from this time view.",
                {"filter": saved},
            )
        if saved == "photos":
            return Result("ready", "Showing photos.", {"filter": saved})
        return Result("ready", "Showing stills.", {"filter": saved})

    def reset_defaults(self) -> Result:
        from semblon.app_reset import reset_app_to_defaults

        rec = reset_app_to_defaults(self.store)
        if not rec.ok:
            raise AdapterError("reset.FAILED", rec.message or "Reset could not finish.")
        return Result(
            "ready",
            "Reset finished. Display settings and caches were cleared. The library was kept.",
            {"cleared": list(rec.cleared), "skipped": list(rec.skipped)},
        )

    def inspect_pack(self, path: str) -> Result:
        import os

        from semblon.knowledge import PackError, load_pack

        file_path = Path(path)
        if not file_path.is_file():
            return Result("unavailable", "Choose a reference file on this computer.", {})
        try:
            pack = load_pack(file_path)
        except (PackError, OSError, ValueError) as exc:
            raise AdapterError("pack.INVALID", str(exc)) from exc
        if not pack:
            return Result("unavailable", "That file is not a reference Semblon can use.", {})
        os.environ["SEMBLON_LKG_PACK"] = str(file_path.resolve())
        count = len(pack.get("entries") or [])
        return Result("ready", f"Reference notes loaded ({count}).", {"count": count, "path": str(file_path)})

    def install_model_file(self, source: str, dest: str) -> Result:
        from semblon.model_install import InstallError, install_model

        try:
            rec = install_model(Path(source), Path(dest))
        except InstallError as exc:
            raise AdapterError("model.INSTALL", str(exc)) from exc
        return Result("ready", "That extra piece is installed on this computer.", {"path": rec.get("path"), "state": rec.get("state")})

    def install_region_pack(self) -> Result:
        """User-confirmed one-click installer for the pinned region encoder."""
        from semblon.region_pack_install import RegionPackInstallError, install_region_pack

        try:
            rec = install_region_pack()
        except RegionPackInstallError as exc:
            raise AdapterError("region_pack.INSTALL", str(exc), state="unavailable") from exc
        changed = bool(rec.get("changed"))
        message = (
            "The piece that finds a similar look is ready. Semblon will try that search again."
            if changed
            else "That piece was already here. Semblon will try the similar-look search again."
        )
        return Result(
            "ready",
            message,
            {
                "path": rec.get("path"),
                "sha256": rec.get("sha256"),
                "state": rec.get("state"),
                "changed": changed,
            },
        )

    def install_object_pack(self) -> Result:
        """User-confirmed one-click installer for the pinned object model."""
        from semblon.object_pack_install import ObjectPackInstallError, install_object_pack

        try:
            rec = install_object_pack()
        except ObjectPackInstallError as exc:
            raise AdapterError("object_pack.INSTALL", str(exc), state="unavailable") from exc
        changed = bool(rec.get("changed"))
        message = (
            "Semblon can now look for things in pictures. That search will run again."
            if changed
            else "Looking for things in pictures was already ready. That search will run again."
        )
        return Result(
            "ready",
            message,
            {
                "path": rec.get("path"),
                "sha256": rec.get("sha256"),
                "state": rec.get("state"),
                "changed": changed,
            },
        )

    def install_vlm(self) -> Result:
        """User-confirmed install of the local description marker. No download."""
        from semblon.vlm_model import VlmInstallError, install_local_description

        try:
            rec = install_local_description()
        except VlmInstallError as exc:
            raise AdapterError("vlm.INSTALL", str(exc), state="unavailable") from exc
        changed = bool(rec.get("changed"))
        message = (
            "Semblon can now describe a picture. That will run again."
            if changed
            else "Describing a picture was already ready. It will run again."
        )
        return Result(
            "ready",
            message,
            {"path": rec.get("path"), "state": rec.get("state"), "changed": changed},
        )

    def named_items(self) -> Result:
        """User-drawn regions. These are not people and do not confirm identity."""
        rows = self._app.regions()
        items = []
        for row in rows:
            label = str(row.get("named") or "").strip() or "Unnamed item"
            items.append(
                {
                    "item_id": str(row.get("item_id") or ""),
                    "label": label,
                    "media_id": str(row.get("media_id") or ""),
                }
            )
        if not items:
            return Result("empty", "Named items: none saved yet.", {"items": []})
        return Result("ready", f"Named items: {len(items)} saved.", {"items": items})

    def name_named_item(self, item_id: str, name: str) -> Result:
        who = str(name or "").strip()
        if not who:
            raise AdapterError("region.NAME", "Named items: a name is required.")
        if not str(item_id or "").strip():
            raise AdapterError("region.NAME", "Named items: choose an item first.")
        try:
            self._app.name_region(item_id, who)
        except Exception as exc:
            raise AdapterError("region.NAME", str(exc)) from exc
        return Result("ready", f"Named items: saved {who}.", {"item_id": item_id, "label": who})
