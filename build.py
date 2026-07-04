#!/usr/bin/env python3
"""
Build script for BIOS Database site.

Reads data/*.json — one file per manufacturer, with BIOSes nested under
consoles — and generates:
  - index.html                — searchable list of manufacturers (small payload)
  - m/<slug>.html             — one page per manufacturer with their BIOS entries

Per-manufacturer data files mean PRs stay tiny, merge conflicts stay rare,
and there are no integer IDs for contributors to coordinate on.
"""

import json
import re
import shutil
from pathlib import Path

ROOT = Path(__file__).parent
DATA_DIR = ROOT / "data"
OUTPUT_INDEX = ROOT / "index.html"
MFR_DIR = ROOT / "m"


def slugify(name: str) -> str:
    s = name.lower().strip()
    s = re.sub(r"[^a-z0-9]+", "-", s)
    s = re.sub(r"-+", "-", s).strip("-")
    return s or "unknown"


def load_manufacturers():
    """Load every data/*.json file and validate its shape."""
    manufacturers = []
    for path in sorted(DATA_DIR.glob("*.json")):
        with open(path, "r", encoding="utf-8") as f:
            try:
                doc = json.load(f)
            except json.JSONDecodeError as e:
                raise SystemExit(f"[{path.name}] invalid JSON: {e}")
        if "manufacturer" not in doc or "consoles" not in doc:
            raise SystemExit(f"[{path.name}] missing 'manufacturer' or 'consoles' field")
        manufacturers.append(doc)
    if not manufacturers:
        raise SystemExit(f"No data files found in {DATA_DIR}")
    return manufacturers


def build_index_payload(manufacturers):
    """Summary payload for index.html — no BIOS hash data, keeps it small."""
    out = []
    for doc in manufacturers:
        consoles = sorted(doc["consoles"], key=lambda c: c["longName"].lower())
        entry_count = sum(len(c.get("bioses", [])) for c in consoles)
        out.append({
            "name": doc["manufacturer"],
            "slug": slugify(doc["manufacturer"]),
            "consoleCount": len(consoles),
            "entryCount": entry_count,
            "consoles": [
                {"longName": c["longName"], "shortName": c.get("shortName") or ""}
                for c in consoles
            ],
        })
    out.sort(key=lambda m: m["name"].lower())
    return out


def flatten_manufacturer(doc):
    """Flatten one manufacturer doc into rows for its table page."""
    rows = []
    for console in doc["consoles"]:
        long_name = console["longName"]
        short_name = console.get("shortName") or ""
        for bios in console.get("bioses", []):
            rows.append({
                "longName": long_name,
                "shortName": short_name,
                "name": bios.get("name", ""),
                "altName": bios.get("altName") or "",
                "region": bios.get("region") or "",
                "version": bios.get("version") or "",
                "size": bios.get("size"),
                "md5": bios.get("md5") or "",
                "sha1": bios.get("sha1") or "",
                "sha256": bios.get("sha256") or "",
                "notes": bios.get("notes") or "",
            })
    rows.sort(key=lambda r: (r["longName"].lower(), r["name"].lower()))
    return rows


SHARED_STYLES = r"""
  :root {
    --bg: #0f1115;
    --panel: #171a21;
    --panel-2: #1e222b;
    --border: #2a2f3a;
    --text: #e6e8ec;
    --muted: #8b93a7;
    --accent: #4ea1ff;
    --accent-dim: #2b6cb0;
    --mono: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
  }
  * { box-sizing: border-box; }
  html, body { margin: 0; padding: 0; background: var(--bg); color: var(--text);
    font-family: system-ui, -apple-system, "Segoe UI", Roboto, sans-serif; }
  a { color: var(--accent); text-decoration: none; }
  a:hover { text-decoration: underline; }
  header { padding: 24px 20px 12px; border-bottom: 1px solid var(--border); }
  header .container { max-width: 1200px; margin: 0 auto; }
  header h1 { margin: 0 0 4px; font-size: 22px; letter-spacing: 0.2px; }
  header p { margin: 0; color: var(--muted); font-size: 14px; }
  .crumbs { font-size: 13px; color: var(--muted); margin-bottom: 6px; }
  .container { max-width: 1200px; margin: 0 auto; padding: 20px; }
  .search-bar { position: sticky; top: 0; background: var(--bg); padding: 16px 0 12px;
    z-index: 10; display: flex; gap: 10px; flex-wrap: wrap; align-items: center; }
  .search-bar input, .search-bar select {
    background: var(--panel); color: var(--text); border: 1px solid var(--border);
    border-radius: 8px; padding: 10px 12px; font-size: 14px; outline: none;
  }
  .search-bar input:focus, .search-bar select:focus { border-color: var(--accent); }
  #search { flex: 1; min-width: 220px; }
  .count { color: var(--muted); font-size: 13px; margin-left: auto; }
  .no-results { padding: 40px; text-align: center; color: var(--muted); }
  footer { text-align: center; padding: 30px 20px; color: var(--muted); font-size: 12px; }
  footer a { color: var(--accent); }
"""

INDEX_TEMPLATE = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>The BIOS Database</title>
<style>
__SHARED_STYLES__
  .mfr-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
    gap: 12px; margin-top: 8px; }
  .mfr-card { background: var(--panel); border: 1px solid var(--border); border-radius: 10px;
    padding: 16px; transition: 0.15s; display: block; color: var(--text); }
  .mfr-card:hover { border-color: var(--accent-dim); text-decoration: none;
    transform: translateY(-1px); }
  .mfr-name { font-size: 17px; font-weight: 600; margin-bottom: 6px; }
  .mfr-stats { color: var(--muted); font-size: 12.5px; margin-bottom: 10px; }
  .mfr-consoles { color: var(--muted); font-size: 13px; line-height: 1.5; }
  .mfr-consoles .console-chip { display: inline-block; background: var(--panel-2);
    border: 1px solid var(--border); border-radius: 6px; padding: 2px 8px;
    margin: 2px 4px 2px 0; font-size: 12px; color: var(--text); }
</style>
</head>
<body>
<header>
  <div class="container">
    <h1>The BIOS Database</h1>
    <p>A dataset of MD5, SHA1, and SHA256 hashes for game console and computer BIOS files. Pick a manufacturer to browse.</p>
  </div>
</header>
<div class="container">
  <div class="search-bar">
    <input type="text" id="search" placeholder="Search manufacturers or consoles..." autofocus>
    <span class="count" id="count"></span>
  </div>
  <div class="mfr-grid" id="grid"></div>
  <div class="no-results" id="no-results" style="display:none;">No matching manufacturers.</div>
</div>
<footer>
  Edit files in <code>data/</code> via pull request to contribute.
  Site built automatically by GitHub Actions.
</footer>

<script>
const MANUFACTURERS = __MANUFACTURERS__;

const $ = (id) => document.getElementById(id);
const searchEl = $("search");
const grid = $("grid");
const countEl = $("count");
const noResults = $("no-results");

function escapeHtml(s) {
  return String(s).replace(/[&<>"']/g, c => ({
    "&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"
  }[c]));
}

function renderCard(m) {
  const chips = m.consoles.slice(0, 6).map(c => {
    const label = c.shortName || c.longName;
    return `<span class="console-chip">${escapeHtml(label)}</span>`;
  }).join("");
  const more = m.consoles.length > 6 ? `<span class="console-chip">+${m.consoles.length - 6} more</span>` : "";
  return `<a class="mfr-card" href="m/${escapeHtml(m.slug)}.html">
    <div class="mfr-name">${escapeHtml(m.name)}</div>
    <div class="mfr-stats">${m.consoleCount} console${m.consoleCount === 1 ? '' : 's'} · ${m.entryCount} BIOS entr${m.entryCount === 1 ? 'y' : 'ies'}</div>
    <div class="mfr-consoles">${chips}${more}</div>
  </a>`;
}

function filterAndRender() {
  const q = searchEl.value.trim().toLowerCase();
  const filtered = MANUFACTURERS.filter(m => {
    if (!q) return true;
    if (m.name.toLowerCase().includes(q)) return true;
    return m.consoles.some(c =>
      c.longName.toLowerCase().includes(q) ||
      (c.shortName || "").toLowerCase().includes(q)
    );
  });
  grid.innerHTML = filtered.map(renderCard).join("");
  countEl.textContent = filtered.length + " of " + MANUFACTURERS.length + " manufacturers";
  noResults.style.display = filtered.length === 0 ? "block" : "none";
}

filterAndRender();
searchEl.addEventListener("input", filterAndRender);
</script>
</body>
</html>
"""

MFR_TEMPLATE = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>__MFR_NAME__ - The BIOS Database</title>
<style>
__SHARED_STYLES__
  .console-card { background: var(--panel); border: 1px solid var(--border); border-radius: 10px;
    margin-bottom: 12px; overflow: hidden; }
  .console-card > summary { cursor: pointer; padding: 14px 16px; display: flex;
    align-items: center; justify-content: space-between; gap: 12px; list-style: none;
    font-size: 15px; font-weight: 600; user-select: none; }
  .console-card > summary::-webkit-details-marker { display: none; }
  .console-card > summary::after { content: "\25BE"; color: var(--muted);
    transition: transform 0.15s; flex-shrink: 0; }
  .console-card[open] > summary::after { transform: rotate(180deg); }
  .console-card > summary:hover { background: var(--panel-2); }
  .console-meta { color: var(--muted); font-weight: 400; font-size: 12.5px; }
  table { width: 100%; border-collapse: collapse; margin-top: 8px;
    background: var(--panel); border-radius: 10px; overflow: hidden;
    border: 1px solid var(--border); }
  .console-card table { margin-top: 0; border-radius: 0; border: none; background: transparent;
    border-top: 1px solid var(--border); }
  thead th { background: var(--panel-2); text-align: left; padding: 10px 12px;
    font-size: 12px; text-transform: uppercase; letter-spacing: 0.5px;
    color: var(--muted); border-bottom: 1px solid var(--border); }
  tbody td { padding: 10px 12px; border-bottom: 1px solid var(--border); font-size: 14px; vertical-align: top; }
  tbody tr:last-child td { border-bottom: none; }
  tbody tr:hover { background: rgba(78,161,255,0.05); }
  .hash { font-family: var(--mono); font-size: 12.5px; color: #cfd6e4;
    word-break: break-all; display: inline-flex; align-items: center; gap: 6px; }
  .hash button { background: transparent; border: 1px solid var(--border); color: var(--muted);
    border-radius: 6px; padding: 2px 6px; font-size: 11px; cursor: pointer; transition: 0.15s; }
  .hash button:hover { color: var(--accent); border-color: var(--accent-dim); }
  .hash button.copied { color: #58d68d; border-color: #58d68d; }
  .empty { color: var(--muted); font-style: italic; }
  .region-tag { display: inline-block; background: var(--panel-2); padding: 2px 8px;
    border-radius: 999px; font-size: 12px; color: var(--muted); border: 1px solid var(--border); }
  .size { font-family: var(--mono); font-size: 12.5px; color: #cfd6e4; white-space: nowrap; }
  .alt-name { color: var(--muted); font-size: 12px; margin-top: 2px; }
  .notes { color: var(--muted); font-size: 12.5px; max-width: 260px; }
  @media (max-width: 800px) {
    thead { display: none; }
    tbody tr { display: block; padding: 12px; border-bottom: 1px solid var(--border); }
    tbody td { display: block; padding: 4px 0; border: none; }
    tbody td::before { content: attr(data-label); display: block; font-size: 11px;
      text-transform: uppercase; color: var(--muted); margin-top: 6px; }
  }
</style>
</head>
<body>
<header>
  <div class="container">
    <div class="crumbs"><a href="../index.html">← All manufacturers</a></div>
    <h1>__MFR_NAME__</h1>
    <p>__SUMMARY__</p>
  </div>
</header>
<div class="container">
  <div class="search-bar">
    <input type="text" id="search" placeholder="Search BIOS name, console, region, hash..." autofocus>
    <select id="region-filter">
      <option value="">All regions</option>
    </select>
    <span class="count" id="count"></span>
  </div>
  <div id="table-wrap">
    <div id="consoles"></div>
    <div class="no-results" id="no-results" style="display:none;">No matching entries.</div>
  </div>
</div>
<footer>
  Edit <code>data/__MFR_SLUG__.json</code> via pull request to contribute.
</footer>

<script>
const DATA = __DATA__;

const $ = (id) => document.getElementById(id);
const searchEl = $("search");
const regionEl = $("region-filter");
const consolesEl = $("consoles");
const countEl = $("count");
const noResults = $("no-results");
const openState = {};

function escapeHtml(s) {
  return String(s).replace(/[&<>"']/g, c => ({
    "&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"
  }[c]));
}

function formatSize(bytes) {
  if (bytes == null) return null;
  if (bytes < 1024) return bytes + " B";
  const units = ["KiB", "MiB", "GiB", "TiB"];
  let v = bytes / 1024;
  let i = 0;
  while (v >= 1024 && i < units.length - 1) { v /= 1024; i++; }
  const decimals = v >= 100 ? 0 : v >= 10 ? 1 : 2;
  return v.toFixed(decimals) + " " + units[i];
}

function populateFilters() {
  const regions = [...new Set(DATA.map(r => r.region).filter(Boolean))].sort();
  for (const r of regions) {
    const opt = document.createElement("option");
    opt.value = r; opt.textContent = r;
    regionEl.appendChild(opt);
  }
}

function groupByConsole(rows) {
  const map = new Map();
  for (const r of rows) {
    const key = r.longName + "|" + r.shortName;
    if (!map.has(key)) map.set(key, { key, longName: r.longName, shortName: r.shortName, rows: [] });
    map.get(key).rows.push(r);
  }
  return [...map.values()];
}

const GROUPS = groupByConsole(DATA);

function hashCell(value) {
  if (!value) return '<span class="empty">—</span>';
  const v = escapeHtml(value);
  return `<span class="hash"><span class="hash-value">${v}</span>` +
         `<button onclick="copyHash(this, '${v}')">copy</button></span>`;
}

window.copyHash = function(btn, value) {
  navigator.clipboard.writeText(value).then(() => {
    const old = btn.textContent;
    btn.textContent = "copied";
    btn.classList.add("copied");
    setTimeout(() => { btn.textContent = old; btn.classList.remove("copied"); }, 1200);
  });
};

function renderRow(r) {
  const alt = r.altName ? `<div class="alt-name">${escapeHtml(r.altName)}</div>` : "";
  const region = r.region ? `<span class="region-tag">${escapeHtml(r.region)}</span>` : '<span class="empty">—</span>';
  const version = r.version ? escapeHtml(r.version) : '<span class="empty">—</span>';
  const sizeFmt = formatSize(r.size);
  const sizeCell = sizeFmt
    ? `<span class="size" title="${r.size} bytes">${escapeHtml(sizeFmt)}</span>`
    : '<span class="empty">—</span>';
  const notes = r.notes ? escapeHtml(r.notes) : "";
  return `<tr>
    <td data-label="BIOS">
      <div>${escapeHtml(r.name)}</div>
      ${alt}
    </td>
    <td data-label="Region">${region}</td>
    <td data-label="Version">${version}</td>
    <td data-label="Size">${sizeCell}</td>
    <td data-label="MD5">${hashCell(r.md5)}</td>
    <td data-label="SHA1">${hashCell(r.sha1)}</td>
    <td data-label="SHA256">${hashCell(r.sha256)}</td>
    <td data-label="Notes" class="notes">${notes}</td>
  </tr>`;
}

function renderConsoleCard(g, rows, isOpen) {
  const title = g.shortName
    ? `${escapeHtml(g.longName)} <span class="console-meta">(${escapeHtml(g.shortName)})</span>`
    : escapeHtml(g.longName);
  return `<details class="console-card" data-key="${escapeHtml(g.key)}"${isOpen ? " open" : ""}>
    <summary>
      <span>${title}</span>
      <span class="console-meta">${rows.length} BIOS${rows.length === 1 ? "" : "es"}</span>
    </summary>
    <table>
      <thead>
        <tr>
          <th>BIOS</th>
          <th>Region</th>
          <th>Version</th>
          <th>Size</th>
          <th>MD5</th>
          <th>SHA1</th>
          <th>SHA256</th>
          <th>Notes</th>
        </tr>
      </thead>
      <tbody>${rows.map(renderRow).join("")}</tbody>
    </table>
  </details>`;
}

function filterAndRender() {
  const q = searchEl.value.trim().toLowerCase();
  const region = regionEl.value;
  const filtersActive = !!q || !!region;

  let totalMatches = 0;
  const cards = GROUPS.map(g => {
    const nameMatches = q && (g.longName.toLowerCase().includes(q) || g.shortName.toLowerCase().includes(q));
    const rows = g.rows.filter(r => {
      if (region && r.region !== region) return false;
      if (!q || nameMatches) return true;
      const sizeFmt = formatSize(r.size) || "";
      const haystack = [
        r.name, r.altName, r.region, r.version, sizeFmt, r.md5, r.sha1, r.sha256, r.notes
      ].join(" ").toLowerCase();
      return haystack.includes(q);
    });
    if (rows.length === 0) return "";
    totalMatches += rows.length;
    const isOpen = openState[g.key] !== undefined ? openState[g.key] : filtersActive;
    return renderConsoleCard(g, rows, isOpen);
  }).join("");

  consolesEl.innerHTML = cards;
  countEl.textContent = totalMatches + " of " + DATA.length + " entries";
  noResults.style.display = totalMatches === 0 ? "block" : "none";
}

consolesEl.addEventListener("toggle", (e) => {
  if (e.target.matches("details.console-card")) {
    openState[e.target.dataset.key] = e.target.open;
  }
}, true);

populateFilters();
filterAndRender();
searchEl.addEventListener("input", filterAndRender);
regionEl.addEventListener("change", filterAndRender);
</script>
</body>
</html>
"""


def write_index(index_payload):
    payload = json.dumps(index_payload, ensure_ascii=False)
    html_out = (INDEX_TEMPLATE
                .replace("__SHARED_STYLES__", SHARED_STYLES)
                .replace("__MANUFACTURERS__", payload))
    OUTPUT_INDEX.write_text(html_out, encoding="utf-8")


def write_manufacturer_page(doc):
    rows = flatten_manufacturer(doc)
    slug = slugify(doc["manufacturer"])
    console_count = len({r["longName"] for r in rows}) or len(doc["consoles"])
    summary = (f"{len(rows)} BIOS entr{'y' if len(rows) == 1 else 'ies'} "
               f"across {console_count} console{'' if console_count == 1 else 's'}.")
    payload = json.dumps(rows, ensure_ascii=False)
    html_out = (MFR_TEMPLATE
                .replace("__SHARED_STYLES__", SHARED_STYLES)
                .replace("__MFR_NAME__", doc["manufacturer"])
                .replace("__MFR_SLUG__", slug)
                .replace("__SUMMARY__", summary)
                .replace("__DATA__", payload))
    (MFR_DIR / f"{slug}.html").write_text(html_out, encoding="utf-8")


def main():
    manufacturers = load_manufacturers()

    if MFR_DIR.exists():
        shutil.rmtree(MFR_DIR)
    MFR_DIR.mkdir(parents=True)

    write_index(build_index_payload(manufacturers))
    for doc in manufacturers:
        write_manufacturer_page(doc)

    total_entries = sum(
        len(c.get("bioses", []))
        for doc in manufacturers
        for c in doc["consoles"]
    )
    print(f"Wrote index.html + {len(manufacturers)} manufacturer page(s) "
          f"({total_entries} BIOS entries total)")


if __name__ == "__main__":
    main()
