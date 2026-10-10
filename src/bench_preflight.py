"""Preflight checks for the physical UNO R4 -> host bench capture."""

from pathlib import Path
import platform
import subprocess
import tempfile

from src.board_live import PortSelectionError, choose_serial_port


def _port_record(port):
    return {
        "device": str(getattr(port, "device", "") or ""),
        "description": str(getattr(port, "description", "") or ""),
        "manufacturer": str(getattr(port, "manufacturer", "") or ""),
        "product": str(getattr(port, "product", "") or ""),
        "hwid": str(getattr(port, "hwid", "") or ""),
    }


def _git_state(repo_root):
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
        return {"revision": None, "dirty": None}
    return {"revision": revision or None, "dirty": dirty}


def _load_ports():
    try:
        from serial.tools import list_ports
    except ImportError as exc:
        raise RuntimeError("pyserial is not installed") from exc
    return list(list_ports.comports())


def _probe_output_root(output_root):
    root = Path(output_root)
    root.mkdir(parents=True, exist_ok=True)
    try:
        with tempfile.NamedTemporaryFile(
            prefix=".bench-preflight-",
            dir=str(root),
            delete=True,
        ) as handle:
            handle.write(b"ok")
            handle.flush()
    except OSError as exc:
        raise RuntimeError(
            "output root is not writable: {}".format(root)
        ) from exc
    return str(root)


def run_preflight(
    port="auto",
    output_root="results/bench",
    repo_root=".",
    port_provider=None,
    output_probe=None,
):
    errors = []
    warnings = []

    provider = port_provider or _load_ports
    probe = output_probe or _probe_output_root

    try:
        ports = list(provider())
    except RuntimeError as exc:
        ports = []
        errors.append(str(exc))

    inventory = [_port_record(item) for item in ports]
    selected = None

    if not errors:
        if port == "auto":
            try:
                selected = choose_serial_port(ports)
            except PortSelectionError as exc:
                errors.append(str(exc))
        else:
            matches = [
                item.device for item in ports
                if str(item.device).casefold() == str(port).casefold()
            ]
            if matches:
                selected = matches[0]
            else:
                errors.append(
                    "requested serial port is not present: {}".format(port)
                )

    try:
        writable_root = probe(output_root)
    except (OSError, RuntimeError) as exc:
        writable_root = None
        errors.append(str(exc))

    git = _git_state(repo_root)
    if git["dirty"] is True:
        warnings.append(
            "working tree is dirty; baseline capture will record git_dirty=true"
        )
    if git["revision"] is None:
        warnings.append("Git revision could not be determined")

    return {
        "ok": not errors,
        "python_version": platform.python_version(),
        "requested_port": port,
        "selected_port": selected,
        "serial_ports": inventory,
        "output_root": writable_root,
        "git_revision": git["revision"],
        "git_dirty": git["dirty"],
        "warnings": warnings,
        "errors": errors,
    }


def format_preflight(result):
    state = "PASS" if result["ok"] else "FAIL"
    selected = result.get("selected_port") or "-"
    line = "PREFLIGHT {} selected_port={}".format(state, selected)
    if result.get("warnings"):
        line += " warnings={}".format("; ".join(result["warnings"]))
    if result.get("errors"):
        line += " errors={}".format("; ".join(result["errors"]))
    return line
