#!/usr/bin/env python3
"""
Check one or more hashes against the BIOS database.

If any given hash matches a known BIOS entry, the other given hashes are
cross-checked against that same entry's recorded values, and any mismatch
is reported as a warning. If none of the given hashes match anything in
the database, it's reported as entirely unknown.

Hash type (md5/sha1/sha256/crc32) is auto-detected from each value's
length, so hashes can be given in any order and don't need to be labeled.

Usage:
  python check_hashes.py <hash> [<hash> ...]

Example:
  python check_hashes.py a860e8c0b6d573d191e4ec7db1b1e4f6 300c20df6731a33952ded8c436f7f186d25d3492
"""

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).parent
DATA_DIR = ROOT / "data"

HASH_LENGTHS = {32: "md5", 40: "sha1", 64: "sha256", 8: "crc32"}
HEX_RE = re.compile(r"^[0-9a-fA-F]+$")


def load_entries():
    entries = []
    for path in sorted(DATA_DIR.glob("*.json")):
        doc = json.loads(path.read_text(encoding="utf-8"))
        mfr = doc.get("manufacturer", path.stem)
        for console in doc.get("consoles", []):
            console_name = console.get("longName", "?")
            for bios in console.get("bioses", []):
                entries.append({
                    "manufacturer": mfr,
                    "console": console_name,
                    "name": bios.get("name", "?"),
                    "hashes": {
                        "md5": (bios.get("md5") or "").lower() or None,
                        "sha1": (bios.get("sha1") or "").lower() or None,
                        "sha256": (bios.get("sha256") or "").lower() or None,
                        "crc32": (bios.get("crc32") or "").lower() or None,
                    },
                })
    return entries


def build_index(entries):
    index = {"md5": {}, "sha1": {}, "sha256": {}, "crc32": {}}
    for entry in entries:
        for htype, value in entry["hashes"].items():
            if value:
                index[htype].setdefault(value, []).append(entry)
    return index


def classify(raw):
    value = raw.strip().lower()
    if not HEX_RE.match(value):
        return None, value
    return HASH_LENGTHS.get(len(value)), value


def describe(entry):
    return f"{entry['manufacturer']} / {entry['console']} / {entry['name']}"


def main(argv):
    if not argv:
        print(__doc__)
        return 2

    inputs = []
    for raw in argv:
        htype, value = classify(raw)
        if htype is None:
            print(f"Skipping '{raw}': not a recognized hash length (expected 8, 32, 40, or 64 hex chars).")
            continue
        inputs.append((htype, value))

    if not inputs:
        print("No valid hashes given.")
        return 2

    index = build_index(load_entries())

    matched_entries = {}
    for htype, value in inputs:
        for entry in index[htype].get(value, []):
            matched_entries[id(entry)] = entry

    if not matched_entries:
        print("All hashes are unknown — no match found in the database.")
        return 0

    if len(matched_entries) > 1:
        print("Warning: the given hashes match MULTIPLE different known files:")
        for entry in matched_entries.values():
            print(f"  - {describe(entry)}")
        print("These hashes don't all belong to the same known file.")
        return 1

    entry = next(iter(matched_entries.values()))
    print(f"Match found: {describe(entry)}\n")

    mismatches = 0
    unverifiable = 0
    for htype, value in inputs:
        known = entry["hashes"].get(htype)
        label = htype.upper()
        if known is None:
            print(f"  {label}: {value}  — no known {label} on file for this entry, cannot verify")
            unverifiable += 1
        elif known == value:
            print(f"  {label}: {value}  OK")
        else:
            print(f"  {label}: {value}  MISMATCH (expected {known})")
            mismatches += 1

    print()
    if mismatches:
        print(f"{mismatches} hash(es) do NOT match the known values for this file.")
        return 1
    if unverifiable == len(inputs):
        print("None of the given hash types are on file for this entry — matched by identity only.")
    elif unverifiable:
        print("No mismatches found, but not every hash could be verified (see above).")
    else:
        print("All provided hashes are consistent with this known file.")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
