# The BIOS Database

A static, searchable website hosted on GitHub Pages that provides MD5, SHA1, and SHA256 hashes for game console and computer BIOS files.

This has been "vibe coded" with human verification, the initial datasets were generated using AI to cross-reference mulitple datasets.

The aim is to have a simple front-end for users to reference to aid searching/validating; as I found this information being sporadic with things being based on release groups etc 

The side effect is that the json datasets should be nice for automated tooling to parse too.

## How it works

- **Data lives in `data/<manufacturer>.json`** — one file per manufacturer, with BIOSes nested under their consoles. Human-readable, edited via git pull requests.
- **`build.py`** reads every `data/*.json` file and generates:
  - `index.html` — a searchable card grid of manufacturers (small payload, loads fast).
  - `m/<slug>.html` — one page per manufacturer, holding only that manufacturer's BIOS entries.
- **GitHub Actions** rebuilds and deploys automatically on every push to `main`.

Per-manufacturer files keep PRs tiny, avoid merge conflicts when multiple people contribute at once, and eliminate the need for contributors to coordinate on integer IDs. Per-manufacturer HTML pages keep each page's client-side dataset small, so search stays snappy even as the database grows.

## Schema

Each `data/<manufacturer>.json` file looks like this:

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

**BIOS fields:** `name` (required), plus optional `altName`, `region`, `version`, `size`, `md5`, `sha1`, `sha256`, `crc32`, `notes`. Use `null` for any optional field that isn't known. The `size` field is a raw byte count (integer), which the site formats as B, KiB, MiB, GiB, or TiB automatically. `crc32` is stored for contributors who cross-reference DAT-based tools (No-Intro, Redump, clrmamepro) but is not displayed on the site.

## Adding a BIOS entry

1. Open the relevant `data/<manufacturer>.json` (or create a new file if the manufacturer doesn't exist yet).
2. Find the matching console's `bioses` array — or add a new console object if needed.
3. Append the new BIOS object with the fields you know. Set unknown fields to `null`.
4. Commit and push (or open a PR). GitHub Actions will rebuild and deploy.

The filename determines the manufacturer's page URL — e.g. `data/sony.json` → `m/sony.html`. Keep filenames lowercase and use hyphens for spaces.

## Local preview

```bash
pip install -r requirements.txt
python build.py
# then open index.html in your browser
# or serve locally so relative links to m/*.html work everywhere:
python -m http.server 8000
```

## Notes and links

Freeform Markdown notes and external links can be added alongside the hash data, kept in a separate `notes/` directory so the JSON stays clean for automated tooling. These are always supplementary — rendered after the primary content (the manufacturer grid, or the BIOS table), not before it:

- `notes/_index.md` — shown at the bottom of the site's index page.
- `notes/<manufacturer-slug>.md` — shown at the bottom of that manufacturer's page.
- `notes/<manufacturer-slug>/<console-slug>.md` — shown inside that console's card, below its BIOS table.

All three are entirely optional — add one only where you have something worth saying (background, links to further reading, expected filenames for emulators, etc). Slugs must match the manufacturer name / console `longName` the same way `data/<manufacturer>.json` filenames do; `python validate.py` will flag a note file that doesn't match anything. See `notes/_index.md`, `notes/sony.md`, and `notes/sony/playstation.md` for examples.

## Checking a hash

`check_hashes.py` looks up one or more hashes against `data/*.json` without needing a build. Hash type (MD5/SHA1/SHA256/CRC32) is auto-detected by length, so you can pass them in any order:

```bash
python check_hashes.py a860e8c0b6d573d191e4ec7db1b1e4f6 300c20df6731a33952ded8c436f7f186d25d3492
```

If any given hash matches a known entry, the rest are cross-checked against that entry's recorded values, and a mismatch is flagged as a warning. If nothing matches this site's data, it falls back to checking [libretro-database](https://github.com/libretro/libretro-database)'s `dat/System.dat` (fetched over the network and cached in `.cache/`) before reporting the hashes as entirely unknown. Pass `--offline` to skip that fallback, or `--refresh-dats` to force re-downloading the cached copy.

## First-time GitHub setup

1. Push this repo to GitHub.
2. Go to **Settings → Pages → Build and deployment**.
3. Set **Source** to **GitHub Actions**.
4. Push to `main` — the workflow will build and deploy the site.

## Features

- Instant client-side search on both the index and per-manufacturer pages.
- Filter by console and region on manufacturer pages.
- One-click copy for any hash value.
- Light/Dark/Auto theme toggle (defaults to dark, remembered via localStorage).
- Mobile-friendly responsive layout.
- Zero runtime dependencies — pure static HTML/CSS/JS.
