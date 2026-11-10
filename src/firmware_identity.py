"""Generate a source-and-build-recipe identity for UNO R4 firmware."""

import hashlib
import json
from pathlib import Path
import subprocess


_GENERATED = {
    "build_identity.h",
    "firmware_build_identity.json",
}


def firmware_source_files(firmware_dir):
    firmware_dir = Path(firmware_dir)
    files = []
    for path in firmware_dir.iterdir():
        if not path.is_file() or path.name in _GENERATED:
            continue
        if path.suffix.lower() not in {".ino", ".h", ".hpp", ".c", ".cpp"}:
            continue
        files.append(path)
    return sorted(files, key=lambda path: path.name)


def source_sha256(firmware_dir):
    digest = hashlib.sha256()
    files = firmware_source_files(firmware_dir)
    if not files:
        raise ValueError("no firmware source files found")
    root = Path(firmware_dir)
    for path in files:
        relative = path.relative_to(root).as_posix().encode("utf-8")
        digest.update(len(relative).to_bytes(4, "big"))
        digest.update(relative)
        data = path.read_bytes()
        digest.update(len(data).to_bytes(8, "big"))
        digest.update(data)
    return digest.hexdigest(), [path.name for path in files]


def build_recipe_context(
    *,
    cli_version,
    core_version,
    fqbn,
    cli_asset_id=None,
    cli_executable_sha256=None,
):
    return {
        "arduino_cli_version": str(cli_version),
        "arduino_cli_asset": (
            None if cli_asset_id is None else str(cli_asset_id)
        ),
        "arduino_cli_executable_sha256": (
            None
            if cli_executable_sha256 is None
            else str(cli_executable_sha256).lower()
        ),
        "arduino_core_version": str(core_version),
        "fqbn": str(fqbn),
    }


def build_context_sha256(build_context):
    if build_context is None:
        return None
    if not isinstance(build_context, dict):
        raise ValueError("firmware build context must be a JSON object")
    encoded = json.dumps(
        build_context,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def git_state(repo_root):
    try:
        revision = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=repo_root,
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()
        dirty = bool(
            subprocess.run(
                ["git", "status", "--porcelain"],
                cwd=repo_root,
                check=True,
                capture_output=True,
                text=True,
            ).stdout.strip()
        )
    except (OSError, subprocess.CalledProcessError):
        return None, None
    return revision or None, dirty


def build_identity(
    firmware_dir,
    repo_root=".",
    revision=None,
    dirty=None,
    build_context=None,
):
    firmware_dir = Path(firmware_dir)
    if revision is None or dirty is None:
        detected_revision, detected_dirty = git_state(repo_root)
        if revision is None:
            revision = detected_revision
        if dirty is None:
            dirty = detected_dirty

    source_hash, source_files = source_sha256(firmware_dir)
    context_hash = build_context_sha256(build_context)
    revision_token = "nogit" if not revision else str(revision)[:12]
    build_id = "g{}-s{}".format(revision_token, source_hash[:12])
    if context_hash is not None:
        build_id += "-b{}".format(context_hash[:12])
    if dirty is True:
        build_id += "-dirty"

    return {
        "build_id": build_id,
        "git_revision": revision,
        "git_dirty": dirty,
        "source_sha256": source_hash,
        "source_files": source_files,
        "build_context_sha256": context_hash,
        "build_context": build_context,
    }


def write_identity_files(
    firmware_dir,
    repo_root=".",
    revision=None,
    dirty=None,
    build_context=None,
):
    firmware_dir = Path(firmware_dir)
    identity = build_identity(
        firmware_dir,
        repo_root=repo_root,
        revision=revision,
        dirty=dirty,
        build_context=build_context,
    )
    header = firmware_dir / "build_identity.h"
    manifest = firmware_dir / "firmware_build_identity.json"
    header.write_text(
        "#pragma once\n"
        '#define SECURITY_FIRMWARE_BUILD_ID "{}"\n'.format(
            identity["build_id"]
        ),
        encoding="utf-8",
    )
    manifest.write_text(
        json.dumps(identity, indent=2) + "\n",
        encoding="utf-8",
    )
    return identity
