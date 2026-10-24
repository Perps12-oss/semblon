"""Dependency and capability preflight.

Reports pinned packages, optional capabilities, and gates. Installs only when
a caller names one id. A satisfied pin is skipped. Model weights are not
downloaded from a report. Identity thresholds are not read or written.
"""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

_MARKER = re.compile(
    r"""python_version\s*(<=|>=|==|<|>)\s*['"](\d+)\.(\d+)['"]"""
)
_ROOT = Path(__file__).resolve().parents[1]


def _row(**fields: object) -> dict:
    item = {
        "id": "",
        "name": "",
        "purpose": "",
        "kind": "python",
        "required": False,
        "status": "missing",
        "installable": False,
        "detail": "",
        "version": "",
        "found": "",
        "confirm": "",
        "downloads": False,
    }
    item.update(fields)
    item["itemId"] = item["id"]
    return item


def _cmp(left: tuple[int, int], op: str, right: tuple[int, int]) -> bool:
    if op == "<":
        return left < right
    if op == "<=":
        return left <= right
    if op == ">":
        return left > right
    if op == ">=":
        return left >= right
    if op == "==":
        return left == right
    return False


def marker_applies(marker: str, python_version: tuple[int, int]) -> bool | None:
    """True when the marker matches. None when this checker cannot read it."""
    text = marker.strip()
    if not text:
        return True
    match = _MARKER.fullmatch(text)
    if match is None:
        return None
    op, major, minor = match.group(1), int(match.group(2)), int(match.group(3))
    return _cmp(python_version, op, (major, minor))


def parse_pins(text: str, *, python_version: tuple[int, int]) -> list[dict]:
    """Pinned ``name==version`` lines that apply to this Python.

    ``-r`` includes are not followed. Unpinned lines are reported and are not
    install targets. Version numbers come only from the file that was passed.
    """
    found: list[dict] = []
    for raw in text.splitlines():
        line = raw.split("#", 1)[0].strip()
        if not line or line.startswith("-r"):
            continue
        spec, _, marker = line.partition(";")
        spec = spec.strip()
        applies = marker_applies(marker, python_version)
        name = spec.split("==", 1)[0].split(">=", 1)[0].split("<=", 1)[0].strip()
        if applies is None:
            found.append(
                _row(
                    id=f"pkg:{name.lower()}",
                    name=name,
                    purpose="Declared dependency",
                    kind="python",
                    status="unverifiable",
                    detail=f"Could not read the environment marker on {spec}.",
                    version=spec,
                )
            )
            continue
        if not applies:
            continue
        if "==" not in spec:
            found.append(
                _row(
                    id=f"pkg:{name.lower()}",
                    name=name,
                    purpose="Declared dependency",
                    kind="python",
                    status="unverifiable",
                    detail=f"{spec} is not an exact pin, so preflight will not install it.",
                    version=spec,
                )
            )
            continue
        package, version = (part.strip() for part in spec.split("==", 1))
        found.append(
            _row(
                id=f"pkg:{package.lower()}",
                name=package,
                purpose="Required by the project pin",
                kind="python",
                required=True,
                version=version,
            )
        )
    return found


def _canon(name: str) -> str:
    return name.strip().lower().replace("_", "-")


def installed_distributions() -> dict[str, str]:
    from importlib.metadata import distributions

    found: dict[str, str] = {}
    for dist in distributions():
        name = dist.metadata.get("Name") or ""
        if name:
            found[_canon(name)] = dist.version
    return found


def _read_error(exc: BaseException) -> str:
    text = str(exc).strip() or type(exc).__name__
    if text == type(exc).__name__:
        return text
    return f"{type(exc).__name__}: {text}"


def _failed_required(item_id: str, name: str, purpose: str, error: str) -> dict:
    return _row(
        id=item_id,
        name=name,
        purpose=purpose,
        kind="python",
        required=True,
        status="failed",
        installable=False,
        detail=error,
    )


def _python_rows(
    pins: list[dict],
    installed: dict[str, str],
    *,
    venv: bool,
    kind: str,
    required: bool,
) -> list[dict]:
    rows: list[dict] = []
    for pin in pins:
        if pin["status"] == "unverifiable":
            row = dict(pin)
            row["kind"] = kind
            row["required"] = required and pin.get("required", False)
            rows.append(row)
            continue
        name = _canon(str(pin["name"]))
        found = installed.get(name, "")
        version = str(pin["version"])
        if not found:
            status = "missing"
            detail = f"{pin['name']} {version} is not installed in this environment."
        elif found == version:
            status = "ready"
            detail = f"{pin['name']} {version} is already installed."
        else:
            status = "incompatible"
            detail = f"Found {pin['name']} {found}. The pin requires {version}."
        installable = venv and status in {"missing", "incompatible"}
        if not venv and status != "ready":
            detail += " Preflight will not change system Python."
        rows.append(
            _row(
                id=pin["id"],
                name=str(pin["name"]),
                purpose=str(pin["purpose"]),
                kind=kind,
                required=required,
                status=status,
                installable=installable,
                detail=detail,
                version=version,
                found=found,
                confirm=(
                    f"Install {pin['name']}=={version} into this environment only. "
                    "Other packages are left as they are."
                ),
                downloads=False,
            )
        )
    return rows


def _invoke(fn):
    """Run one probe. A raised error is returned, not discarded."""
    try:
        return fn(), None
    except Exception as exc:  # noqa: BLE001 — the row must show the real failure
        text = str(exc).strip() or type(exc).__name__
        return None, f"{type(exc).__name__}: {text}" if text != type(exc).__name__ else text


def _failed_probe(probe_id: str, name: str, purpose: str, kind: str, error: str) -> dict:
    return _row(
        id=probe_id,
        name=name,
        purpose=purpose,
        kind=kind,
        required=False,
        status="failed",
        installable=False,
        detail=f"{name} could not be checked. {error}",
    )


def _capability_rows(probes: dict) -> list[dict]:
    rows: list[dict] = []

    result, error = _invoke(probes["region"])
    if error is not None:
        rows.append(_failed_probe("region_pack", "Region model", "Semantic look of a selected area", "model", error))
    else:
        ready, note = result
        rows.append(
            _row(
                id="region_pack",
                name="Region model",
                purpose="Semantic look of a selected area",
                kind="model",
                status="ready" if ready else "missing",
                installable=not ready,
                detail=(
                    "The pinned region model is installed."
                    if ready
                    else (note or "Region model is missing.")
                    + " Colour-only search is a separate fallback, not this capability."
                ),
                confirm=(
                    "Download the pinned region model into the Semblon model folder. "
                    "This does not change face identity."
                ),
                downloads=not ready,
            )
        )

    result, error = _invoke(probes["object"])
    if error is not None:
        rows.append(_failed_probe("object_pack", "Object model", "Object labels in a photo", "model", error))
    else:
        ready, note = result
        rows.append(
            _row(
                id="object_pack",
                name="Object model",
                purpose="Object labels in a photo",
                kind="model",
                status="ready" if ready else "missing",
                installable=not ready,
                detail="The pinned object model is installed."
                if ready
                else (note or "Object model is missing."),
                confirm=(
                    "Download the pinned object model into the Semblon model folder. "
                    "This does not change face identity."
                ),
                downloads=not ready,
            )
        )

    result, error = _invoke(probes["vlm"])
    if error is not None:
        rows.append(_failed_probe("vlm_local", "Description", "A local description of a selection", "model", error))
        vlm = ""
    else:
        vlm = str(result or "MISSING")
    if vlm == "AVAILABLE":
        vlm_status, vlm_install, vlm_detail = "ready", False, "Local description is installed."
    elif vlm == "DISABLED":
        vlm_status, vlm_install, vlm_detail = (
            "blocked",
            False,
            "Description is turned off. Preflight will not switch it on.",
        )
    else:
        vlm_status, vlm_install, vlm_detail = (
            "missing",
            True,
            "Description model is not installed. This setup writes a local marker and does not download weights.",
        )
    if error is None:
        rows.append(
            _row(
                id="vlm_local",
                name="Description",
                purpose="A local description of a selection",
                kind="model",
                status=vlm_status,
                installable=vlm_install,
                detail=vlm_detail,
                confirm="Write the local description marker. This does not download weights.",
                downloads=False,
            )
        )

    result, error = _invoke(probes["ocr"])
    if error is not None:
        rows.append(_failed_probe("ocr", "Text in photos", "Read words in a photo", "tool", error))
    else:
        ready, note = result
        rows.append(
        _row(
            id="ocr",
            name="Text in photos",
            purpose="Read words in a photo",
            kind="tool",
            status="ready" if ready else "missing",
            installable=False,
            detail="Text recognition is available."
            if ready
            else (
                (note or "Text recognition is not available.")
                + " The OCR extra is not an exact pin, and Tesseract is a separate program. "
                "Preflight will not install either one."
            ),
        )
        )

    result, error = _invoke(probes["clip"])
    if error is not None:
        rows.append(_failed_probe("clip", "CLIP semantics", "Optional semantic observer", "model", error))
    else:
        ready, note = result
        rows.append(
        _row(
            id="clip",
            name="CLIP semantics",
            purpose="Optional semantic observer",
            kind="model",
            status="ready" if ready else "missing",
            installable=False,
            detail="Local CLIP weights are available."
            if ready
            else (
                (note or "CLIP is not available.")
                + " The first weight download is a deliberate human step. This check does not contact the network."
            ),
        )
        )

    result, error = _invoke(probes["face"])
    if error is not None:
        rows.append(
            _failed_probe(
                "face_pack",
                "Face model",
                "Detect faces and compare them on the active pack",
                "model",
                error,
            )
        )
    else:
        face_ok, face_note = result
        rows.append(
        _row(
            id="face_pack",
            name="Face model",
            purpose="Detect faces and compare them on the active pack",
            kind="model",
            status="ready" if face_ok else "missing",
            installable=False,
            detail="YuNet and SFace are present and pinned."
            if face_ok
            else (
                (face_note or "Face weights are missing.")
                + " Semblon does not download identity weights. Place the files locally, then run "
                "semblon lab pack-accept. Adding face files does not name anyone."
            ),
        )
        )

    result, error = _invoke(probes["opencv_load"])
    if error is not None:
        rows.append(
            _failed_probe(
                "opencv_load",
                "OpenCV load",
                "Native image library used by ingest and search",
                "native",
                error,
            )
        )
    else:
        loaded, found_version, load_error = result
        rows.append(
        _row(
            id="opencv_load",
            name="OpenCV load",
            purpose="Native image library used by ingest and search",
            kind="native",
            status="ready" if loaded else "incompatible",
            installable=False,
            detail=(
                f"OpenCV {found_version} loaded."
                if loaded
                else f"The OpenCV package did not load ({load_error or 'load failed'}). "
                "A successful package install is not the same as a loadable native library."
            ),
            found=str(found_version or ""),
        )
        )

    result, error = _invoke(probes["arch"])
    if error is not None:
        rows.append(
            _failed_probe(
                "architecture",
                "Python architecture",
                "Whether this interpreter is the native build for this PC",
                "native",
                error,
            )
        )
    else:
        execution, arch = result
        native = execution == "native"
        rows.append(
        _row(
            id="architecture",
            name="Python architecture",
            purpose="Whether this interpreter is the native build for this PC",
            kind="native",
            status="ready" if native else "unverifiable",
            installable=False,
            detail=(
                f"This interpreter is native {arch}."
                if native
                else f"This interpreter is {execution} {arch}. Native ARM64 qualification is separate and is not claimed."
            ),
            found=f"{execution}/{arch}",
        )
    )

    rows.append(
        _row(
            id="authenticode",
            name="Installer signing",
            purpose="Release signature for the Windows installer",
            kind="gate",
            status="blocked",
            installable=False,
            detail="A signing certificate is not an installable dependency.",
        )
    )
    rows.append(
        _row(
            id="model_licence",
            name="Model licensing",
            purpose="Permission to redistribute identity and detector weights",
            kind="gate",
            status="blocked",
            installable=False,
            detail="Licensing approval is not an installable dependency. Bring-your-own weights stay in place.",
        )
    )
    return rows


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def default_probes() -> dict:
    def region():
        from semblon.region_encoder import probe_region_pack

        return probe_region_pack()

    def object_pack():
        from semblon.object_pack import probe_nanodet_status

        return probe_nanodet_status()

    def vlm():
        from semblon.lens import probe_vlm

        return probe_vlm()

    def ocr():
        from semblon.observers import probe_ocr_status

        return probe_ocr_status()

    def clip():
        from semblon.observers import probe_clip_status

        return probe_clip_status()

    def face():
        from semblon.engine import ModelPackError, assert_face_pack_ready

        try:
            assert_face_pack_ready()
        except ModelPackError as exc:
            return False, str(exc)
        return True, None

    def opencv_load():
        try:
            import cv2
            import numpy as np

            image = np.zeros((2, 2, 3), dtype=np.uint8)
            cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
            return True, str(cv2.__version__), None
        except Exception as exc:  # noqa: BLE001 — load failure is the status
            return False, "", _read_error(exc)

    def arch():
        from semblon.engine import process_arch, process_execution

        return process_execution(), process_arch()

    return {
        "region": region,
        "object": object_pack,
        "vlm": vlm,
        "ocr": ocr,
        "clip": clip,
        "face": face,
        "opencv_load": opencv_load,
        "arch": arch,
    }


def collect_rows(
    *,
    runtime_text: str | None = None,
    dev_text: str | None = None,
    python_version: tuple[int, int] | None = None,
    installed: dict[str, str] | None = None,
    venv: bool | None = None,
    probes: dict | None = None,
) -> list[dict]:
    py = python_version or sys.version_info[:2]
    managed = (sys.prefix != sys.base_prefix) if venv is None else venv
    versions: dict[str, str] | None
    if installed is not None:
        versions = installed
        meta_error = ""
    else:
        try:
            versions = installed_distributions()
            meta_error = ""
        except Exception as exc:  # noqa: BLE001 — a metadata failure must not look like missing pins
            versions = None
            meta_error = f"Installed packages could not be read. {_read_error(exc)}"

    def _pins(text: str | None, filename: str) -> tuple[list[dict], str]:
        if text is not None:
            return parse_pins(text, python_version=py), ""
        try:
            return parse_pins(_read(_ROOT / filename), python_version=py), ""
        except OSError as exc:
            return [], f"Could not read {filename}. {_read_error(exc)}"

    runtime, runtime_error = _pins(runtime_text, "requirements.txt")
    dev_pins, dev_error = _pins(dev_text, "requirements-dev.txt")
    runtime_ids = {row["id"] for row in runtime}
    dev_only = [row for row in dev_pins if row["id"] not in runtime_ids]
    if versions is None:
        rows = [
            _failed_required(
                "pkg:metadata",
                "Installed packages",
                "Versions already present in this environment",
                meta_error,
            )
        ]
    else:
        rows = _python_rows(runtime, versions, venv=managed, kind="python", required=True)
        rows.extend(_python_rows(dev_only, versions, venv=managed, kind="tool", required=False))
    if runtime_error:
        rows.append(
            _failed_required(
                "pins:requirements.txt",
                "requirements.txt",
                "Pinned runtime packages",
                runtime_error,
            )
        )
    if dev_error:
        rows.append(
            _row(
                id="pins:requirements-dev.txt",
                name="requirements-dev.txt",
                purpose="Pinned development tools",
                kind="tool",
                required=False,
                status="failed",
                installable=False,
                detail=dev_error,
            )
        )
    if probes is None:
        rows.extend(_capability_rows(default_probes()))
    elif probes:
        rows.extend(_capability_rows(probes))
    return rows


def required_gaps(**kwargs: object) -> list[dict]:
    """Required rows that are not ready. Does not install. Omits model probes unless given."""
    kwargs.setdefault("probes", {})
    return [
        row
        for row in collect_rows(**kwargs)  # type: ignore[arg-type]
        if row["required"] and row["status"] != "ready"
    ]


def capability_rows(**kwargs: object) -> list[dict]:
    """Capabilities a person can set up or must be told about. Ready native rows stay out."""
    return [
        row
        for row in collect_rows(**kwargs)  # type: ignore[arg-type]
        if row["status"] == "failed"
        or (row["kind"] in {"model", "tool", "native"} and row["status"] != "ready")
    ]


def _default_pip_install(spec: str) -> None:
    if sys.prefix == sys.base_prefix:
        raise RuntimeError("refusing to change system Python")
    completed = subprocess.run(
        [sys.executable, "-m", "pip", "install", spec],
        check=False,
        capture_output=True,
        text=True,
    )
    if completed.returncode != 0:
        lines = [
            line.strip()
            for line in (completed.stderr or completed.stdout or "").splitlines()
            if line.strip()
        ]
        detail = " | ".join(lines[-8:]) if lines else f"pip exited {completed.returncode}"
        if len(detail) > 500:
            detail = detail[-500:]
        raise RuntimeError(detail)


def _default_installers() -> dict:
    def region():
        from semblon.region_pack_install import install_region_pack

        return install_region_pack()

    def objects():
        from semblon.object_pack_install import install_object_pack

        return install_object_pack()

    def vlm():
        from semblon.vlm_model import install_local_description

        return install_local_description()

    return {
        "region_pack": region,
        "object_pack": objects,
        "vlm_local": vlm,
    }


def install_item(
    item_id: str,
    *,
    runtime_text: str | None = None,
    dev_text: str | None = None,
    python_version: tuple[int, int] | None = None,
    installed: dict[str, str] | None = None,
    venv: bool | None = None,
    probes: dict | None = None,
    installers: dict | None = None,
    pip_install=None,
    cancel=None,
) -> dict:
    """Install one id, then verify. Ready items are skipped. Failure stays unresolved."""
    if cancel is not None and cancel():
        return {
            "id": item_id,
            "status": "cancelled",
            "ready": False,
            "skipped": False,
            "error": "Install cancelled.",
        }
    kwargs = {
        "runtime_text": runtime_text,
        "dev_text": dev_text,
        "python_version": python_version,
        "installed": installed,
        "venv": venv,
        "probes": probes,
    }
    current = {row["id"]: row for row in collect_rows(**kwargs)}
    row = current.get(item_id)
    if row is None:
        return {
            "id": item_id,
            "status": "failed",
            "ready": False,
            "skipped": False,
            "error": f"Unknown dependency {item_id}.",
        }
    if row["status"] == "ready":
        return {
            "id": item_id,
            "status": "ready",
            "ready": True,
            "skipped": True,
            "error": "",
        }
    if not row["installable"]:
        return {
            "id": item_id,
            "status": row["status"],
            "ready": False,
            "skipped": False,
            "error": row["detail"],
        }
    actions = dict(_default_installers())
    if installers:
        actions.update(installers)
    try:
        if item_id.startswith("pkg:"):
            installer = pip_install or _default_pip_install
            installer(f"{row['name']}=={row['version']}")
        else:
            action = actions.get(item_id)
            if action is None:
                return {
                    "id": item_id,
                    "status": "blocked",
                    "ready": False,
                    "skipped": False,
                    "error": row["detail"] or "No installer is registered for this item.",
                }
            action()
    except Exception as exc:  # noqa: BLE001 — the caller must see the real failure
        return {
            "id": item_id,
            "status": "failed",
            "ready": False,
            "skipped": False,
            "error": str(exc) or type(exc).__name__,
        }
    if cancel is not None and cancel():
        return {
            "id": item_id,
            "status": "cancelled",
            "ready": False,
            "skipped": False,
            "error": "Install cancelled before verification.",
        }
    verified = {item["id"]: item for item in collect_rows(**kwargs)}.get(item_id)
    if verified is not None and verified["status"] == "ready":
        return {"id": item_id, "status": "ready", "ready": True, "skipped": False, "error": ""}
    return {
        "id": item_id,
        "status": "failed",
        "ready": False,
        "skipped": False,
        "error": (verified or {}).get("detail") or "Installed files did not verify.",
    }
