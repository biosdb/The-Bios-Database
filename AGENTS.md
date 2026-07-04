# AGENTS.md

Instructions for AI coding agents working on this repository.

## What this repo is

A static site hosted on GitHub Pages that lets people look up MD5, SHA1, and SHA256 hashes for game console and computer BIOS files. It is generated from JSON files by a Python build script and deployed by GitHub Actions.

There is no backend, no database, no runtime dependencies. Everything is static HTML/CSS/JS produced at build time from the JSON in `data/`.

## Repository layout

```
.
├── AGENTS.md                    ← this file
├── README.md                    ← human-facing docs
├── build.py                     ← generator: reads data/*.json → writes index.html + m/*.html
├── validate.py                  ← data integrity checker (run in CI on PRs)
├── data/
│   ├── <manufacturer>.json      ← one file per manufacturer (source of truth)
│   └── ...
├── index.html                   ← GENERATED — do not edit by hand
├── m/
│   └── <slug>.html              ← GENERATED — do not edit by hand
└── .github/workflows/
    ├── build.yml                ← deploys to GitHub Pages on push to main
    └── validate.yml             ← validates data/*.json on pull requests
```

## Commands

| Task | Command |
|---|---|
| Build the site | `python build.py` |
| Validate all data files | `python validate.py` |
| Preview locally | `python -m http.server 8000` (after building) |

Both scripts use only the Python 3 standard library. Do not add third-party dependencies without a strong reason.

## Data model

Each `data/<manufacturer>.json` follows this exact shape:

```json
{
  "manufacturer": "Sony",
  "consoles": [
    {
      "shortName": "PS1",
      "longName": "PlayStation",
      "bioses": [
        {
          "name": "SCPH-1001",
          "altName": "PlayStation NTSC-U BIOS",
          "region": "NTSC-U",
          "version": "2.2",
          "size": 524288,
          "md5": "8dd7d5296a650fac7319bce665a6a53c",
          "sha1": "10155d8d6e6e832d6ea66db9bc098321fb5e8ebf",
          "sha256": null,
          "crc32": null,
          "notes": "Original US BIOS, released 1995"
        }
      ]
    }
  ]
}
```

**Required fields:** `manufacturer` (top level), `consoles[].longName`, `consoles[].bioses[].name`.

**Optional fields** (set to `null`, never omit): `shortName`, `altName`, `region`, `version`, `size`, `md5`, `sha1`, `sha256`, `crc32`, `notes`.

**Hash format:** lowercase hex only. MD5 = 32 chars, SHA1 = 40 chars, SHA256 = 64 chars, CRC32 = 8 chars. `null` if unknown — do not invent values.

**CRC32** is intentionally not shown in the web UI (it's too short to add real verification power alongside MD5/SHA1/SHA256 at this dataset's size) but is kept in the data for contributors cross-referencing DAT-based tools (No-Intro, Redump, clrmamepro) that key off it.

**Size format:** raw byte count as a non-negative integer (e.g. `524288` for a 512 KiB BIOS), or `null` if unknown. The site formats it for display using binary units (B, KiB, MiB, GiB, TiB) — do not pre-format the value.

**No integer IDs anywhere.** Consoles and BIOSes are identified by their position in the nested structure.

## Adding a BIOS entry

1. Locate the correct file: `data/<manufacturer>.json` (lowercase, hyphens for spaces).
2. If the file doesn't exist, create it with the shape above.
3. Find the console object in `consoles[]` whose `longName` matches. If it doesn't exist, add it.
4. Append the new BIOS object to that console's `bioses[]` array.
5. Run `python validate.py` to check. Then `python build.py` to preview.
6. Only commit changes under `data/`. Do not commit generated `index.html` or `m/*.html`.

## Rules for agents

**Do**
- Edit only files under `data/` when adding or correcting BIOS data.
- Run `python validate.py` before committing any data change.
- Keep JSON formatted with 2-space indent and a trailing newline (the existing files are the reference).
- Use `null` for unknown optional fields — never empty strings, never omit the key.
- Match the filename to the manufacturer name (lowercased, hyphens for spaces). `data/sony.json`, `data/atari.json`, `data/nec-home-electronics.json`.

**Do not**
- Do not edit `index.html` or files under `m/`. They are regenerated on every build; hand edits will be lost.
- Do not invent hash values. If a hash isn't known and verified, use `null`.
- Do not add new fields to the schema without also updating `build.py`, `validate.py`, and both HTML templates.
- Do not add third-party Python packages — the workflows install nothing beyond stdlib Python 3.12.
- Do not add `id` fields or foreign keys. The nested structure is intentional.
- Do not rename manufacturer files without also checking that no external site links to the old URL, since `data/foo.json` maps directly to `m/foo.html`.

## Schema changes

If you must change the schema:
1. Update the shape in every file under `data/`.
2. Update `flatten_manufacturer()` and `build_index_payload()` in `build.py`.
3. Update the corresponding template(s) — `INDEX_TEMPLATE` and/or `MFR_TEMPLATE` in `build.py`.
4. Update the validation rules in `validate.py`.
5. Update the schema section in `README.md` and this file.
6. Run `python validate.py && python build.py` and confirm both succeed.

## CI behavior

- **On pull request:** `.github/workflows/validate.yml` runs `python validate.py` and `python build.py`. If either fails, the PR is blocked.
- **On push to `main`:** `.github/workflows/build.yml` runs `python build.py` and deploys the result to GitHub Pages.

## Style

- Python: standard library only, type hints where it aids clarity, no external formatter required.
- HTML/CSS/JS in templates: prefer CSS variables for colors (already defined in `SHARED_STYLES`), keep JS free of external libraries.
- Keep the generated pages self-contained — a single HTML file per URL, no external requests at runtime.
