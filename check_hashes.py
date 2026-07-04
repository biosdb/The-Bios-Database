#!/usr/bin/env python3
"""
Check one or more hashes against the BIOS database.

If any given hash matches a known BIOS entry, the other given hashes are
cross-checked against that same entry's recorded values, and any mismatch
is reported as a warning. If none of the given hashes match anything in
this site's database, libretro-database's dat/System.dat is checked next
(fetched over the network and cached locally) as a secondary source, since
it covers many BIOS files not yet added to this site. If nothing matches
in either source, it's reported as entirely unknown.

Hash type (md5/sha1/sha256/crc32) is auto-detected from each value's
length, so hashes can be given in any order and don't need to be labeled.

Usage:
  python check_hashes.py [--offline] [--refresh-dats] <hash> [<hash> ...]

Example:
  python check_hashes.py a860e8c0b6d573d191e4ec7db1b1e4f6 300c20df6731a33952ded8c436f7f186d25d3492

Options:
  --offline       Skip the libretro-database lookup entirely (no network access).
  --refresh-dats  Re-download the cached libretro-database dat file before checking.
"""

import json
import re
import sys
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).parent
DATA_DIR = ROOT / "data"
CACHE_DIR = ROOT / ".cache"
LIBRETRO_DAT_CACHE = CACHE_DIR / "libretro-system.dat"
LIBRETRO_DAT_URL = "https://raw.githubusercontent.com/libretro/libretro-database/master/dat/System.dat"
FETCH_TIMEOUT = 10

HASH_LENGTHS = {32: "md5", 40: "sha1", 64: "sha256", 8: "crc32"}
HEX_RE = re.compile(r"^[0-9a-fA-F]+$")
DAT_ROM_RE = re.compile(
    r'rom \( name (".*?"|\S+) size (\d+) crc ([0-9A-Fa-f]{8}) '
    r'md5 ([0-9A-Fa-f]{32}) sha1 ([0-9A-Fa-f]{40}) \)'
)
DAT_COMMENT_RE = re.compile(r'comment "(.*)"')


def load_site_entries():
    entries = []
    for path in sorted(DATA_DIR.glob("*.json")):
        doc = json.loads(path.read_text(encoding="utf-8"))
        mfr = doc.get("manufacturer", path.stem)
        for console in doc.get("consoles", []):
            console_name = console.get("longName", "?")
            for bios in console.get("bioses", []):
                entries.append({
                    "source": "this site",
                    "label": f"{mfr} / {console_name} / {bios.get('name', '?')}",
                    "hashes": {
                        "md5": (bios.get("md5") or "").lower() or None,
                        "sha1": (bios.get("sha1") or "").lower() or None,
                        "sha256": (bios.get("sha256") or "").lower() or None,
                        "crc32": (bios.get("crc32") or "").lower() or None,
                    },
                })
    return entries


def fetch_libretro_dat(refresh=False):
    """Return the dat text, using the local cache unless refresh is requested.
    Returns None (and prints a note) if it can't be fetched and there's no cache."""
    if LIBRETRO_DAT_CACHE.exists() and not refresh:
        return LIBRETRO_DAT_CACHE.read_text(encoding="utf-8", errors="replace")
    try:
        with urllib.request.urlopen(LIBRETRO_DAT_URL, timeout=FETCH_TIMEOUT) as resp:
            text = resp.read().decode("utf-8", errors="replace")
    except (urllib.error.URLError, TimeoutError, OSError) as e:
        if LIBRETRO_DAT_CACHE.exists():
            print(f"Note: couldn't refresh libretro-database dat ({e}); using cached copy.")
            return LIBRETRO_DAT_CACHE.read_text(encoding="utf-8", errors="replace")
        print(f"Note: couldn't fetch libretro-database dat ({e}); skipping that source.")
        return None
    CACHE_DIR.mkdir(exist_ok=True)
    LIBRETRO_DAT_CACHE.write_text(text, encoding="utf-8")
    return text


def parse_libretro_dat(text):
    entries = []
    section = None
    in_game = False
    for line in text.splitlines():
        line = line.strip()
        if line.startswith("game ("):
            in_game = True
            continue
        if not in_game:
            continue
        m = DAT_COMMENT_RE.match(line)
        if m:
            value = m.group(1)
            if value != "System":
                section = value
            continue
        m = DAT_ROM_RE.match(line)
        if m and section:
            name, size, crc, md5, sha1 = m.groups()
            entries.append({
                "source": "libretro-database",
                "label": f"{section} / {name.strip(chr(34))} (not yet in this site's database)",
                "hashes": {"md5": md5.lower(), "sha1": sha1.lower(), "sha256": None, "crc32": crc.lower()},
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


def hash_signature(entry):
    return tuple(entry["hashes"][h] for h in ("md5", "sha1", "sha256", "crc32"))


def find_matches(index, inputs):
    matched = {}
    for htype, value in inputs:
        for entry in index[htype].get(value, []):
            matched[id(entry)] = entry
    return list(matched.values())


def report(entries, inputs):
    """entries: all matches for a single distinct file (same hash signature).
    Returns exit code."""
    labels = [e["label"] for e in entries]
    if len(labels) == 1:
        print(f"Match found ({entries[0]['source']}): {labels[0]}\n")
    else:
        print(f"Match found ({entries[0]['source']}), known under multiple names:")
        for label in labels:
            print(f"  - {label}")
        print()

    combined_hashes = {}
    for e in entries:
        for htype, value in e["hashes"].items():
            if value:
                combined_hashes[htype] = value

    mismatches = 0
    unverifiable = 0
    for htype, value in inputs:
        known = combined_hashes.get(htype)
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


def main(argv):
    offline = "--offline" in argv
    refresh = "--refresh-dats" in argv
    argv = [a for a in argv if a not in ("--offline", "--refresh-dats")]

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

    site_index = build_index(load_site_entries())
    site_matches = find_matches(site_index, inputs)

    if site_matches:
        groups = {}
        for e in site_matches:
            groups.setdefault(hash_signature(e), []).append(e)
        if len(groups) > 1:
            print("Warning: the given hashes match MULTIPLE different known files in this site's database:")
            for group in groups.values():
                for e in group:
                    print(f"  - {e['label']}")
            print("These hashes don't all belong to the same known file.")
            return 1
        return report(next(iter(groups.values())), inputs)

    if offline:
        print("All hashes are unknown in this site's database (libretro-database check skipped: --offline).")
        return 0

    dat_text = fetch_libretro_dat(refresh=refresh)
    if dat_text is None:
        print("All hashes are unknown — no match found in this site's database.")
        return 0

    dat_index = build_index(parse_libretro_dat(dat_text))
    dat_matches = find_matches(dat_index, inputs)

    if not dat_matches:
        print("All hashes are unknown — no match found in this site's database or libretro-database.")
        return 0

    groups = {}
    for e in dat_matches:
        groups.setdefault(hash_signature(e), []).append(e)
    if len(groups) > 1:
        print("Warning: the given hashes match MULTIPLE different known files in libretro-database:")
        for group in groups.values():
            for e in group:
                print(f"  - {e['label']}")
        print("These hashes don't all belong to the same known file.")
        return 1
    return report(next(iter(groups.values())), inputs)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
