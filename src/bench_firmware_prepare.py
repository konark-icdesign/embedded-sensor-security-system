"""Prepare one provenance-bound UNO R4 firmware build for bench capture."""

import re
import shutil
import subprocess
from datetime import datetime, timezone
from pathlib import Path

from src.arduino_toolchain import (
    ARDUINO_CLI_VERSION,
    ARDUINO_CORE_VERSION,
    UNO_R4_WIFI_FQBN,
    cli_asset,
    sha256_file,
)
from src.board_live import discover_serial_port
from src.firmware_build_manifest import (
    build_manifest,
    verify_manifest_artifacts,
    write_manifest,
)
from src.firmware_identity import write_identity_files


CORE_ID = "arduino:renesas_uno"


def parse_cli_version(text):
    match = re.search(r"\bVersion:\s*([0-9]+(?:\.[0-9]+){2})\b", str(text))
    if match is None:
        raise ValueError("could not parse Arduino CLI version")
    return match.group(1)


def parse_installed_core_version(text, core_id=CORE_ID):
    for raw_line in str(text).splitlines():
        line = raw_line.strip()
        if not line or not line.startswith(core_id):
            continue
        fields = line.split()
        if len(fields) < 2:
            break
        return fields[1]
    raise ValueError(
        "installed core was not found in Arduino CLI output: {}".format(
            core_id
        )
    )


def default_cli_path(repo_root, asset_id=None):
    asset = cli_asset(asset_id)
    return Path(repo_root).resolve().parent / "arduino-tools" / asset["executable"]


def default_build_dir(repo_root):
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    return (
        Path(repo_root)
        / "results"
        / "firmware-build"
        / ("prepared-" + stamp)
    )


def _run(command, *, cwd, runner, timeout=300):
    result = runner(
        [str(item) for item in command],
        cwd=str(cwd),
        text=True,
        capture_output=True,
        timeout=timeout,
    )
    if result.returncode:
        detail = (result.stderr or result.stdout or "").strip()
        raise RuntimeError(
            "command failed ({}): {}".format(
                result.returncode,
                detail or "no diagnostic output",
            )
        )
    return result


def prepare_bench_firmware(
    *,
    repo_root,
    build_dir=None,
    manifest_path=None,
    cli_asset_id=None,
    cli_path=None,
    cli_version=ARDUINO_CLI_VERSION,
    core_version=ARDUINO_CORE_VERSION,
    fqbn=UNO_R4_WIFI_FQBN,
    revision=None,
    upload_port=None,
    runner=subprocess.run,
    port_resolver=discover_serial_port,
):
    repo_root = Path(repo_root).resolve()
    firmware_dir = repo_root / "firmware" / "night_security"
    asset = cli_asset(cli_asset_id, cli_version)

    cli_path = (
        Path(cli_path).resolve()
        if cli_path is not None
        else default_cli_path(repo_root, asset["asset_id"])
    )
    if not cli_path.is_file():
        raise RuntimeError(
            "Arduino CLI not found at {}; run "
            "'python scripts/bootstrap_arduino.py' first".format(cli_path)
        )

    version_result = _run(
        [cli_path, "version"],
        cwd=repo_root,
        runner=runner,
        timeout=30,
    )
    actual_cli_version = parse_cli_version(
        "{}\n{}".format(version_result.stdout, version_result.stderr)
    )
    if actual_cli_version != str(cli_version):
        raise RuntimeError(
            "Arduino CLI version mismatch: expected {}, got {}".format(
                cli_version,
                actual_cli_version,
            )
        )

    core_result = _run(
        [cli_path, "core", "list"],
        cwd=repo_root,
        runner=runner,
        timeout=60,
    )
    actual_core_version = parse_installed_core_version(core_result.stdout)
    if actual_core_version != str(core_version):
        raise RuntimeError(
            "UNO R4 core version mismatch: expected {}, got {}".format(
                core_version,
                actual_core_version,
            )
        )

    build_dir = (
        Path(build_dir).resolve()
        if build_dir is not None
        else default_build_dir(repo_root).resolve()
    )
    if build_dir.exists() and any(build_dir.iterdir()):
        raise RuntimeError(
            "build directory is not empty: {}".format(build_dir)
        )
    build_dir.mkdir(parents=True, exist_ok=True)

    identity = write_identity_files(
        firmware_dir,
        repo_root=repo_root,
        revision=revision,
    )

    _run(
        [
            cli_path,
            "compile",
            "--fqbn",
            fqbn,
            "--clean",
            "--output-dir",
            build_dir,
            firmware_dir,
        ],
        cwd=repo_root,
        runner=runner,
        timeout=300,
    )

    cli_executable_sha256 = sha256_file(cli_path)
    manifest_path = (
        Path(manifest_path).resolve()
        if manifest_path is not None
        else build_dir / "firmware_build_manifest.json"
    )
    manifest = build_manifest(
        build_dir,
        firmware_dir / "firmware_build_identity.json",
        cli_version=actual_cli_version,
        core_version=actual_core_version,
        fqbn=fqbn,
        cli_asset_id=asset["asset_id"],
        cli_executable_sha256=cli_executable_sha256,
    )
    write_manifest(manifest_path, manifest)

    verified = verify_manifest_artifacts(manifest_path, build_dir)
    if not verified["ok"]:
        raise RuntimeError("compiled firmware artifact verification failed")

    resolved_port = None
    if upload_port is not None:
        resolved_port = (
            port_resolver()
            if str(upload_port).casefold() == "auto"
            else str(upload_port)
        )
        _run(
            [
                cli_path,
                "upload",
                "-p",
                resolved_port,
                "--fqbn",
                fqbn,
                "--input-dir",
                build_dir,
            ],
            cwd=repo_root,
            runner=runner,
            timeout=180,
        )

    return {
        "ok": True,
        "build_id": identity["build_id"],
        "build_dir": str(build_dir),
        "manifest_path": str(manifest_path),
        "cli_asset": asset["asset_id"],
        "cli_version": actual_cli_version,
        "cli_executable": str(cli_path),
        "cli_executable_sha256": cli_executable_sha256,
        "core_version": actual_core_version,
        "fqbn": fqbn,
        "artifact_count": verified["artifact_count"],
        "uploaded": upload_port is not None,
        "upload_port": resolved_port,
    }
