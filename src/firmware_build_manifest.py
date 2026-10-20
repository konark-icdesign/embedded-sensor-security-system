"""Record hashes and toolchain metadata for compiled UNO R4 artifacts."""

import hashlib
import json
from pathlib import Path

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
            "28a8e119c498a25607821c36cb2dc49e8463941b261a0d99091baa7bc692dd2b"
            if str(cli_version) == "1.5.1"
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
