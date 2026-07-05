#!/usr/bin/env bash
# Compute MD5/SHA1/SHA256/CRC32 hashes for one or more files.
#
# Plain output lists each hash per file. Pass --json to print a JSON array
# of BIOS entry objects (matching data/<manufacturer>.json's schema) with
# the name/size/hash fields filled in and the rest left null, ready to
# paste into a console's "bioses" array for a pull request.
#
# Usage:
#   ./hash_files.sh [--json] <file> [<file> ...]
#
# Example:
#   ./hash_files.sh --json dmg_boot.bin mgb_boot.bin
#
# CRC32 requires python3 or a "crc32" binary on PATH; if neither is
# available it's reported as unavailable (plain mode) or null (--json).

set -euo pipefail

usage() {
  cat >&2 <<'EOF'
Compute MD5/SHA1/SHA256/CRC32 hashes for one or more files.

Plain output lists each hash per file. Pass --json to print a JSON array
of BIOS entry objects (matching data/<manufacturer>.json's schema) with
the name/size/hash fields filled in and the rest left null, ready to
paste into a console's "bioses" array for a pull request.

Usage:
  ./hash_files.sh [--json] <file> [<file> ...]

Example:
  ./hash_files.sh --json dmg_boot.bin mgb_boot.bin

CRC32 requires python3 or a "crc32" binary on PATH; if neither is
available it's reported as unavailable (plain mode) or null (--json).
EOF
  exit 2
}

json_mode=0
files=()
for arg in "$@"; do
  case "$arg" in
    --json) json_mode=1 ;;
    -h|--help) usage ;;
    *) files+=("$arg") ;;
  esac
done

[ "${#files[@]}" -eq 0 ] && usage

file_size() {
  stat -c%s "$1" 2>/dev/null || stat -f%z "$1"
}

hash_md5() {
  if command -v md5sum >/dev/null 2>&1; then md5sum "$1" | awk '{print $1}'
  elif command -v md5 >/dev/null 2>&1; then md5 -q "$1"
  else openssl dgst -md5 -r "$1" | awk '{print $1}'
  fi
}

hash_sha1() {
  if command -v sha1sum >/dev/null 2>&1; then sha1sum "$1" | awk '{print $1}'
  elif command -v shasum >/dev/null 2>&1; then shasum -a 1 "$1" | awk '{print $1}'
  else openssl dgst -sha1 -r "$1" | awk '{print $1}'
  fi
}

hash_sha256() {
  if command -v sha256sum >/dev/null 2>&1; then sha256sum "$1" | awk '{print $1}'
  elif command -v shasum >/dev/null 2>&1; then shasum -a 256 "$1" | awk '{print $1}'
  else openssl dgst -sha256 -r "$1" | awk '{print $1}'
  fi
}

hash_crc32() {
  if command -v python3 >/dev/null 2>&1; then
    python3 -c "
import sys, zlib
data = open(sys.argv[1], 'rb').read()
print(format(zlib.crc32(data) & 0xffffffff, '08x'))
" "$1"
  elif command -v crc32 >/dev/null 2>&1; then
    crc32 "$1"
  else
    echo ""
  fi
}

escape_json_string() {
  local s="$1"
  s="${s//\\/\\\\}"
  s="${s//\"/\\\"}"
  printf '%s' "$s"
}

entries=()
had_error=0
for f in "${files[@]}"; do
  if [ ! -f "$f" ]; then
    echo "Skipping '$f': not a file" >&2
    had_error=1
    continue
  fi

  name=$(basename "$f")
  size=$(file_size "$f")
  md5=$(hash_md5 "$f")
  sha1=$(hash_sha1 "$f")
  sha256=$(hash_sha256 "$f")
  crc32=$(hash_crc32 "$f")

  if [ "$json_mode" -eq 1 ]; then
    esc_name=$(escape_json_string "$name")
    crc32_json="null"
    [ -n "$crc32" ] && crc32_json="\"$crc32\""
    entries+=("$(printf '  {\n    "name": "%s",\n    "altName": null,\n    "region": null,\n    "version": null,\n    "size": %s,\n    "md5": "%s",\n    "sha1": "%s",\n    "sha256": "%s",\n    "crc32": %s,\n    "notes": null\n  }' \
      "$esc_name" "$size" "$md5" "$sha1" "$sha256" "$crc32_json")")
  else
    echo "$name"
    echo "  size:   $size bytes"
    echo "  md5:    $md5"
    echo "  sha1:   $sha1"
    echo "  sha256: $sha256"
    if [ -n "$crc32" ]; then
      echo "  crc32:  $crc32"
    else
      echo "  crc32:  (unavailable — install python3 or a crc32 tool)"
    fi
    echo
  fi
done

if [ "$json_mode" -eq 1 ]; then
  if [ "${#entries[@]}" -eq 0 ]; then
    echo "[]"
  else
    printf '[\n'
    last=$(( ${#entries[@]} - 1 ))
    for i in "${!entries[@]}"; do
      printf '%s' "${entries[$i]}"
      if [ "$i" -lt "$last" ]; then
        printf ',\n'
      else
        printf '\n'
      fi
    done
    printf ']\n'
  fi
fi

[ "$had_error" -eq 0 ]
