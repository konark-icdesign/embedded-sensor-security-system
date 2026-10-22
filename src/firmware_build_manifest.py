"""Record hashes and toolchain metadata for compiled UNO R4 artifacts."""

import hashlib
import json
from pathlib import Path

from src.arduino_toolchain import (
    ARDUINO_CLI_LINUX64_SHA256,
    ARDUINO_CLI_VERSION,
)

FLASH_EXTENSIONS = {".bin", ".hex", ".uf2"}
BUILD_EXTENSIONS = FLASH_EXTENSIONS | {".elf"}


def _sha256(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _load_identity(path):
    try:
        value = json.loads(Path(path).read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise ValueError("firmware build identity manifest not found") from exc
    except json.JSONDecodeError as exc:
        raise ValueError(
            "firmware build identity manifest is not valid JSON"
        ) from exc
    if not isinstance(value, dict) or not value.get("build_id"):
        raise ValueError("firmware build identity manifest is incomplete")
    return value


def collect_artifacts(artifact_dir):
    artifact_dir = Path(artifact_dir)
    rows = []
    for path in sorted(artifact_dir.rglob("*")):
        if not path.is_file() or path.suffix.lower() not in BUILD_EXTENSIONS:
            continue
        rows.append({
            "path": path.relative_to(artifact_dir).as_posix(),
            "bytes": path.stat().st_size,
            "sha256": _sha256(path),
            "flash_candidate": path.suffix.lower() in FLASH_EXTENSIONS,
        })
    if not rows:
        raise ValueError("no compiled firmware artifacts found")
    if not any(row["flash_candidate"] for row in rows):
        raise ValueError("no flashable firmware artifact found")
    return rows


def load_build_manifest(path):
    try:
        value = json.loads(Path(path).read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise ValueError("firmware build manifest not found") from exc
    except json.JSONDecodeError as exc:
        raise ValueError("firmware build manifest is not valid JSON") from exc
    if not isinstance(value, dict):
        raise ValueError("firmware build manifest is not a JSON object")
    if value.get("schema") != 1 or not value.get("firmware_build_id"):
        raise ValueError("firmware build manifest is incomplete")
    artifacts = value.get("artifacts")
    if not isinstance(artifacts, list) or not artifacts:
        raise ValueError("firmware build manifest has no artifacts")
    return value


def verify_manifest_artifacts(manifest_path, artifact_dir):
    manifest = load_build_manifest(manifest_path)
    artifact_dir = Path(artifact_dir)
    results = []
    overall_ok = True

    for expected in manifest["artifacts"]:
        if not isinstance(expected, dict):
            results.append({"ok": False, "error": "invalid artifact record"})
            overall_ok = False
            continue
        name = expected.get("path")
        if not isinstance(name, str):
            results.append({"ok": False, "error": "missing artifact path"})
            overall_ok = False
            continue
        relative = Path(name)
        if relative.is_absolute() or ".." in relative.parts:
            results.append({
                "path": name,
                "ok": False,
                "error": "unsafe artifact path",
            })
            overall_ok = False
            continue

        target = artifact_dir / relative
        if not target.is_file():
            results.append({
                "path": name,
                "ok": False,
                "error": "artifact missing",
            })
            overall_ok = False
            continue

        actual_bytes = target.stat().st_size
        actual_sha256 = _sha256(target)
        expected_bytes = expected.get("bytes")
        expected_sha256 = expected.get("sha256")
        size_ok = (
            isinstance(expected_bytes, int)
            and actual_bytes == expected_bytes
        )
        hash_ok = (
            isinstance(expected_sha256, str)
            and actual_sha256 == expected_sha256.lower()
        )
        row_ok = size_ok and hash_ok
        results.append({
            "path": name,
            "ok": row_ok,
            "bytes_ok": size_ok,
            "sha256_ok": hash_ok,
            "expected_bytes": expected_bytes,
            "actual_bytes": actual_bytes,
            "expected_sha256": expected_sha256,
            "actual_sha256": actual_sha256,
        })
        overall_ok = overall_ok and row_ok

    return {
        "ok": overall_ok,
        "firmware_build_id": manifest["firmware_build_id"],
        "artifact_count": len(results),
        "artifacts": results,
        "manifest": manifest,
    }


def build_manifest(
    artifact_dir,
    identity_path,
    *,
    cli_version,
    core_version,
    fqbn,
):
    identity = _load_identity(identity_path)
    artifacts = collect_artifacts(artifact_dir)
    return {
        "schema": 1,
        "firmware_build_id": identity["build_id"],
        "firmware_source_sha256": identity.get("source_sha256"),
        "firmware_git_revision": identity.get("git_revision"),
        "firmware_git_dirty": identity.get("git_dirty"),
        "arduino_cli_version": str(cli_version),
        "arduino_cli_archive_sha256": (
            ARDUINO_CLI_LINUX64_SHA256
            if str(cli_version) == ARDUINO_CLI_VERSION
            else None
        ),
        "arduino_core_version": str(core_version),
        "fqbn": str(fqbn),
        "artifact_count": len(artifacts),
        "artifacts": artifacts,
        "claim_boundary": (
            "This manifest hashes the compiled files produced by the recorded "
            "toolchain. It proves neither that a particular MCU was flashed "
            "with them nor that the MCU later retained identical bytes."
        ),
    }


def write_manifest(path, value):
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text(
        json.dumps(value, indent=2) + "\n",
        encoding="utf-8",
    )
