# BIOS Hash Lookup

A static, searchable website hosted on GitHub Pages that provides MD5, SHA1, and SHA256 hashes for game console and computer BIOS files.

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
          "notes": "Original US BIOS, released 1995"
        }
      ]
    }
  ]
}
```

**BIOS fields:** `name` (required), plus optional `altName`, `region`, `version`, `size`, `md5`, `sha1`, `sha256`, `notes`. Use `null` for any optional field that isn't known. The `size` field is a raw byte count (integer), which the site formats as B, KiB, MiB, GiB, or TiB automatically.

## Adding a BIOS entry

1. Open the relevant `data/<manufacturer>.json` (or create a new file if the manufacturer doesn't exist yet).
2. Find the matching console's `bioses` array — or add a new console object if needed.
3. Append the new BIOS object with the fields you know. Set unknown fields to `null`.
4. Commit and push (or open a PR). GitHub Actions will rebuild and deploy.

The filename determines the manufacturer's page URL — e.g. `data/sony.json` → `m/sony.html`. Keep filenames lowercase and use hyphens for spaces.

## Local preview

```bash
python build.py
# then open index.html in your browser
# or serve locally so relative links to m/*.html work everywhere:
python -m http.server 8000
```

## First-time GitHub setup

1. Push this repo to GitHub.
2. Go to **Settings → Pages → Build and deployment**.
3. Set **Source** to **GitHub Actions**.
4. Push to `main` — the workflow will build and deploy the site.

## Features

- Instant client-side search on both the index and per-manufacturer pages.
- Filter by console and region on manufacturer pages.
- One-click copy for any hash value.
- Mobile-friendly responsive layout.
- Zero runtime dependencies — pure static HTML/CSS/JS.
