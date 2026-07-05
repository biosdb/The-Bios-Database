#!/usr/bin/env python3
"""
Compute MD5/SHA1/SHA256/CRC32 hashes for one or more files.

Plain output lists each hash per file. Pass --json to print a JSON array
of BIOS entry objects (matching data/<manufacturer>.json's schema) with
the name/size/hash fields filled in and the rest left null, ready to
paste into a console's "bioses" array for a pull request.

Usage:
  python hash_files.py [--json] <file> [<file> ...]

Example:
  python hash_files.py --json dmg_boot.bin mgb_boot.bin
"""

import hashlib
import json
import sys
import zlib
from pathlib import Path

CHUNK_SIZE = 1024 * 1024


def hash_file(path: Path) -> dict:
    md5 = hashlib.md5()
    sha1 = hashlib.sha1()
    sha256 = hashlib.sha256()
    crc32 = 0
    size = 0
    with path.open("rb") as f:
        while True:
            chunk = f.read(CHUNK_SIZE)
            if not chunk:
                break
            size += len(chunk)
            md5.update(chunk)
            sha1.update(chunk)
            sha256.update(chunk)
            crc32 = zlib.crc32(chunk, crc32)
    return {
        "name": path.name,
        "altName": None,
        "region": None,
        "version": None,
        "size": size,
        "md5": md5.hexdigest(),
        "sha1": sha1.hexdigest(),
        "sha256": sha256.hexdigest(),
        "crc32": format(crc32 & 0xFFFFFFFF, "08x"),
        "notes": None,
    }


def print_plain(entry: dict) -> None:
    print(entry["name"])
    print(f"  size:   {entry['size']} bytes")
    print(f"  md5:    {entry['md5']}")
    print(f"  sha1:   {entry['sha1']}")
    print(f"  sha256: {entry['sha256']}")
    print(f"  crc32:  {entry['crc32']}")
    print()


def main(argv):
    json_mode = "--json" in argv
    paths = [a for a in argv if a != "--json"]

    if not paths:
        print(__doc__)
        return 2

    entries = []
    had_error = False
    for raw in paths:
        path = Path(raw)
        if not path.is_file():
            print(f"Skipping '{raw}': not a file", file=sys.stderr)
            had_error = True
            continue
        entries.append(hash_file(path))

    if json_mode:
        print(json.dumps(entries, indent=2))
    else:
        for entry in entries:
            print_plain(entry)

    return 1 if had_error else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
