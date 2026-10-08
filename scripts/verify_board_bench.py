"""Verify SHA-256 integrity for one physical bench capture directory."""

import argparse
import hashlib
import json
from pathlib import Path


def _sha256(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def verify_capture(capture_dir):
    capture_dir = Path(capture_dir)
    manifest_path = capture_dir / "capture_integrity.json"
    if not manifest_path.exists():
        raise ValueError("capture_integrity.json not found")

    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError("capture_integrity.json is not valid JSON") from exc

    if manifest.get("algorithm") != "sha256":
        raise ValueError("unsupported or missing integrity algorithm")

    files = manifest.get("files")
    if not isinstance(files, dict) or not files:
        raise ValueError("integrity manifest has no files")

    results = {}
    overall_ok = True
    for name, expected in files.items():
        if not isinstance(name, str) or Path(name).name != name:
            results[str(name)] = {
                "ok": False,
                "error": "unsafe manifest filename",
            }
            overall_ok = False
            continue
        if not isinstance(expected, dict):
            results[name] = {
                "ok": False,
                "error": "invalid manifest record",
            }
            overall_ok = False
            continue

        target = capture_dir / name
        if not target.is_file():
            results[name] = {
                "ok": False,
                "error": "file missing",
            }
            overall_ok = False
            continue

        actual_bytes = target.stat().st_size
        actual_sha256 = _sha256(target)
        expected_bytes = expected.get("bytes")
        expected_sha256 = expected.get("sha256")
        size_ok = isinstance(expected_bytes, int) and actual_bytes == expected_bytes
        hash_ok = (
            isinstance(expected_sha256, str)
            and actual_sha256 == expected_sha256.lower()
        )
        file_ok = size_ok and hash_ok
        results[name] = {
            "ok": file_ok,
            "bytes_ok": size_ok,
            "sha256_ok": hash_ok,
            "expected_bytes": expected_bytes,
            "actual_bytes": actual_bytes,
            "expected_sha256": expected_sha256,
            "actual_sha256": actual_sha256,
        }
        overall_ok = overall_ok and file_ok

    return {
        "capture": str(capture_dir),
        "ok": overall_ok,
        "algorithm": "sha256",
        "files": results,
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("capture", help="bench capture directory")
    args = parser.parse_args()

    try:
        result = verify_capture(args.capture)
    except ValueError as exc:
        result = {
            "capture": str(Path(args.capture)),
            "ok": False,
            "error": str(exc),
        }

    print(json.dumps(result, indent=2))
    raise SystemExit(0 if result["ok"] else 1)


if __name__ == "__main__":
    main()
