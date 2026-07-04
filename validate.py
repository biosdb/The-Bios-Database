#!/usr/bin/env python3
"""
Validate every data/*.json file for structural correctness.

Checks:
  - Valid JSON
  - Required top-level fields ('manufacturer', 'consoles')
  - Each console has 'longName' and a 'bioses' list
  - Each BIOS has a non-empty 'name'
  - Hash fields (md5, sha1, sha256, crc32) are lowercase hex of the right length, or null
  - Optional fields are present as keys (may be null) — no missing keys
  - No duplicate BIOS 'name' within the same console
  - No duplicate manufacturer slugs across files (would collide on m/<slug>.html)
  - Filename matches the manufacturer's slug (data/sony.json ↔ "Sony")

Exits non-zero on any failure and prints a report of every issue found.
Uses only the Python 3 standard library.
"""

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).parent
DATA_DIR = ROOT / "data"

REQUIRED_BIOS_KEYS = {
    "name", "altName", "region", "version", "size",
    "md5", "sha1", "sha256", "crc32", "notes",
}
HASH_LENGTHS = {"md5": 32, "sha1": 40, "sha256": 64, "crc32": 8}
HEX_RE = re.compile(r"^[0-9a-f]+$")


def slugify(name: str) -> str:
    s = name.lower().strip()
    s = re.sub(r"[^a-z0-9]+", "-", s)
    s = re.sub(r"-+", "-", s).strip("-")
    return s or "unknown"


def validate_hash(field: str, value, errors: list, where: str) -> None:
    if value is None:
        return
    if not isinstance(value, str):
        errors.append(f"{where}: {field} must be a string or null, got {type(value).__name__}")
        return
    expected = HASH_LENGTHS[field]
    if len(value) != expected:
        errors.append(f"{where}: {field} must be {expected} chars, got {len(value)}")
    if not HEX_RE.match(value):
        errors.append(f"{where}: {field} must be lowercase hex, got '{value}'")


def validate_file(path: Path, seen_slugs: dict) -> list:
    errors: list = []
    try:
        doc = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        return [f"{path.name}: invalid JSON — {e}"]

    if not isinstance(doc, dict):
        return [f"{path.name}: top-level value must be an object"]

    mfr = doc.get("manufacturer")
    if not isinstance(mfr, str) or not mfr.strip():
        errors.append(f"{path.name}: 'manufacturer' must be a non-empty string")
        mfr = None

    if mfr:
        slug = slugify(mfr)
        expected_stem = path.stem
        if slug != expected_stem:
            errors.append(
                f"{path.name}: filename stem '{expected_stem}' does not match slug of manufacturer '{mfr}' "
                f"(expected data/{slug}.json)"
            )
        if slug in seen_slugs:
            errors.append(
                f"{path.name}: manufacturer slug '{slug}' collides with {seen_slugs[slug]}"
            )
        else:
            seen_slugs[slug] = path.name

    consoles = doc.get("consoles")
    if not isinstance(consoles, list):
        errors.append(f"{path.name}: 'consoles' must be a list")
        return errors

    for ci, console in enumerate(consoles):
        cwhere = f"{path.name}: consoles[{ci}]"
        if not isinstance(console, dict):
            errors.append(f"{cwhere}: must be an object")
            continue
        long_name = console.get("longName")
        if not isinstance(long_name, str) or not long_name.strip():
            errors.append(f"{cwhere}: 'longName' must be a non-empty string")
        if "shortName" not in console:
            errors.append(f"{cwhere}: missing 'shortName' key (use null if unknown)")
        bioses = console.get("bioses")
        if not isinstance(bioses, list):
            errors.append(f"{cwhere}: 'bioses' must be a list")
            continue

        seen_bios_names: set = set()
        for bi, bios in enumerate(bioses):
            bwhere = f"{cwhere}.bioses[{bi}]"
            if not isinstance(bios, dict):
                errors.append(f"{bwhere}: must be an object")
                continue

            name = bios.get("name")
            if not isinstance(name, str) or not name.strip():
                errors.append(f"{bwhere}: 'name' must be a non-empty string")
            else:
                key = name.strip().lower()
                if key in seen_bios_names:
                    errors.append(f"{bwhere}: duplicate BIOS name '{name}' within this console")
                seen_bios_names.add(key)

            missing = REQUIRED_BIOS_KEYS - set(bios.keys())
            for k in sorted(missing):
                errors.append(f"{bwhere}: missing key '{k}' (use null if unknown)")

            extra = set(bios.keys()) - REQUIRED_BIOS_KEYS
            for k in sorted(extra):
                errors.append(
                    f"{bwhere}: unknown key '{k}' — add it to the schema in build.py "
                    f"and validate.py first, or remove it"
                )

            for hf in HASH_LENGTHS:
                if hf in bios:
                    validate_hash(hf, bios[hf], errors, bwhere)

            for text_field in ("altName", "region", "version", "notes"):
                v = bios.get(text_field)
                if v is not None and not isinstance(v, str):
                    errors.append(f"{bwhere}: '{text_field}' must be a string or null")

            size = bios.get("size")
            if size is not None:
                if isinstance(size, bool) or not isinstance(size, int):
                    errors.append(f"{bwhere}: 'size' must be a non-negative integer (bytes) or null")
                elif size < 0:
                    errors.append(f"{bwhere}: 'size' must be non-negative, got {size}")

    return errors


def main() -> int:
    files = sorted(DATA_DIR.glob("*.json"))
    if not files:
        print(f"No data files found in {DATA_DIR}", file=sys.stderr)
        return 1

    seen_slugs: dict = {}
    all_errors: list = []
    for path in files:
        all_errors.extend(validate_file(path, seen_slugs))

    if all_errors:
        print(f"Found {len(all_errors)} issue(s):", file=sys.stderr)
        for e in all_errors:
            print(f"  - {e}", file=sys.stderr)
        return 1

    total_bioses = 0
    total_consoles = 0
    for path in files:
        doc = json.loads(path.read_text(encoding="utf-8"))
        total_consoles += len(doc["consoles"])
        total_bioses += sum(len(c.get("bioses", [])) for c in doc["consoles"])
    print(f"OK — {len(files)} manufacturer file(s), {total_consoles} console(s), {total_bioses} BIOS entr{'y' if total_bioses == 1 else 'ies'}.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
