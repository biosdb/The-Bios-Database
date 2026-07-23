#!/usr/bin/env python3
"""
Build script for BIOS Database site.

Reads data/*.json — one file per manufacturer, with BIOSes nested under
consoles — and generates:
  - index.html                — searchable list of manufacturers (small payload)
  - m/<slug>.html             — one page per manufacturer with their BIOS entries
  - sitemap.xml               — all URLs for search engine discovery
  - robots.txt                — points crawlers at the sitemap

Per-manufacturer data files mean PRs stay tiny, merge conflicts stay rare,
and there are no integer IDs for contributors to coordinate on.
"""

import json
import re
import shutil
from pathlib import Path

import markdown

ROOT = Path(__file__).parent
DATA_DIR = ROOT / "data"
NOTES_DIR = ROOT / "notes"
OUTPUT_INDEX = ROOT / "index.html"
MFR_DIR = ROOT / "m"

REPO_URL = "https://github.com/biosdb/The-Bios-Database"
SITE_URL = "https://biosdb.github.io/The-Bios-Database"

MD_EXTENSIONS = ["extra", "sane_lists"]


def slugify(name: str) -> str:
    s = name.lower().strip()
    s = re.sub(r"[^a-z0-9]+", "-", s)
    s = re.sub(r"-+", "-", s).strip("-")
    return s or "unknown"


def render_markdown_file(path: Path):
    """Render a Markdown file to HTML, or return None if it doesn't exist / is empty."""
    if not path.is_file():
        return None
    text = path.read_text(encoding="utf-8").strip()
    if not text:
        return None
    return markdown.markdown(text, extensions=MD_EXTENSIONS)


def load_index_notes():
    """notes/_index.md — optional freeform note shown on the site's index page."""
    return render_markdown_file(NOTES_DIR / "_index.md")


def load_manufacturer_notes(mfr_slug: str):
    """notes/<mfr-slug>.md — optional freeform intro shown on the manufacturer page."""
    return render_markdown_file(NOTES_DIR / f"{mfr_slug}.md")


def load_console_notes(mfr_slug: str, console_long_name: str):
    """notes/<mfr-slug>/<console-slug>.md — optional freeform notes/links for one console."""
    console_slug = slugify(console_long_name)
    return render_markdown_file(NOTES_DIR / mfr_slug / f"{console_slug}.md")


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
    --hash-text: #cfd6e4;
    --success: #58d68d;
    --mono: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
  }
  :root[data-theme="light"] {
    --bg: #f6f7f9;
    --panel: #ffffff;
    --panel-2: #eef1f5;
    --border: #dde2e8;
    --text: #1a1d23;
    --muted: #5c6470;
    --accent: #1a66d1;
    --accent-dim: #a9c9f0;
    --hash-text: #33404f;
    --success: #17824f;
  }
  @media (prefers-color-scheme: light) {
    :root[data-theme="system"] {
      --bg: #f6f7f9;
      --panel: #ffffff;
      --panel-2: #eef1f5;
      --border: #dde2e8;
      --text: #1a1d23;
      --muted: #5c6470;
      --accent: #1a66d1;
      --accent-dim: #a9c9f0;
      --hash-text: #33404f;
      --success: #17824f;
    }
  }
  * { box-sizing: border-box; }
  html, body { margin: 0; padding: 0; background: var(--bg); color: var(--text);
    font-family: system-ui, -apple-system, "Segoe UI", Roboto, sans-serif; }
  a { color: var(--accent); text-decoration: none; }
  a:hover { text-decoration: underline; }
  header { position: relative; padding: 24px 20px 12px; border-bottom: 1px solid var(--border); }
  header .container { width: 80%; margin: 0 auto; padding-right: 150px; }
  header h1 { margin: 0 0 4px; font-size: 22px; letter-spacing: 0.2px; }
  header p { margin: 0; color: var(--muted); font-size: 14px; }
  .crumbs { font-size: 13px; color: var(--muted); margin-bottom: 6px; }
  .theme-toggle { position: absolute; top: 20px; right: 20px;
    display: inline-flex; border: 1px solid var(--border); border-radius: 8px; overflow: hidden; }
  .theme-toggle button { background: var(--panel); color: var(--muted); border: none;
    padding: 6px 12px; font-size: 12.5px; font-family: inherit; cursor: pointer; transition: 0.15s; }
  .theme-toggle button + button { border-left: 1px solid var(--border); }
  .theme-toggle button:hover { color: var(--text); background: var(--panel-2); }
  .theme-toggle button.active { background: var(--accent); color: #fff; font-weight: 600; }
  .container { width: 80%; margin: 0 auto; padding: 20px; }
  @media (max-width: 1000px) { .container { width: 100%; } header .container { width: 100%; } }
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
  .page-notes, .console-notes { font-size: 14px; line-height: 1.6; color: var(--text); }
  .page-notes { margin-top: 32px; padding-top: 20px; border-top: 1px solid var(--border); }
  .console-notes { padding: 12px 16px 16px; border-top: 1px solid var(--border); }
  .page-notes > :first-child, .console-notes > :first-child { margin-top: 0; }
  .page-notes > :last-child, .console-notes > :last-child { margin-bottom: 0; }
  .page-notes a, .console-notes a { color: var(--accent); }
  .page-notes ul, .page-notes ol, .console-notes ul, .console-notes ol { padding-left: 22px; }
  .page-notes code, .console-notes code { font-family: var(--mono); font-size: 0.9em;
    background: var(--panel-2); padding: 1px 5px; border-radius: 4px; }
  .page-notes pre, .console-notes pre { background: var(--panel-2); padding: 10px 12px;
    border-radius: 8px; overflow-x: auto; }
  .page-notes pre code, .console-notes pre code { background: none; padding: 0; }
  .page-notes table, .console-notes table { font-size: 13px; }
  .page-notes blockquote, .console-notes blockquote { margin: 0; padding-left: 12px;
    border-left: 3px solid var(--border); color: var(--muted); }
"""

# Applied before first paint so a stored "light"/"dark" preference doesn't
# flash the wrong theme first. Default (no stored preference) is system/auto.
THEME_INIT_SCRIPT = r"""<script>
(function () {
  try {
    document.documentElement.setAttribute("data-theme", localStorage.getItem("theme") || "system");
  } catch (e) {}
})();
</script>"""

THEME_TOGGLE_HTML = r"""<div class="theme-toggle" role="group" aria-label="Theme">
      <button type="button" data-theme-choice="light">Light</button>
      <button type="button" data-theme-choice="dark">Dark</button>
      <button type="button" data-theme-choice="system">Auto</button>
    </div>
    <script>
    (function () {
      var root = document.documentElement;
      var buttons = document.querySelectorAll(".theme-toggle button");
      function apply(theme) {
        root.setAttribute("data-theme", theme);
        try { localStorage.setItem("theme", theme); } catch (e) {}
        buttons.forEach(function (b) { b.classList.toggle("active", b.dataset.themeChoice === theme); });
      }
      var current = root.getAttribute("data-theme") || "system";
      buttons.forEach(function (b) {
        b.classList.toggle("active", b.dataset.themeChoice === current);
        b.addEventListener("click", function () { apply(b.dataset.themeChoice); });
      });
    })();
    </script>"""

INDEX_TEMPLATE = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>The BIOS Database</title>
<link rel="canonical" href="__CANONICAL__">
<link rel="icon" type="image/svg+xml" href="favicon.svg">
__THEME_INIT__
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
  __THEME_TOGGLE__
  <div class="container">
    <div>
      <h1>The BIOS Database</h1>
      <p>A dataset of MD5, SHA1, and SHA256 hashes for game console and computer BIOS files. Pick a manufacturer to browse.</p>
    </div>
  </div>
</header>
<div class="container">
  <div class="search-bar">
    <input type="text" id="search" placeholder="Search manufacturers or consoles..." autofocus>
    <span class="count" id="count"></span>
  </div>
  <div class="mfr-grid" id="grid"></div>
  <div class="no-results" id="no-results" style="display:none;">No matching manufacturers.</div>
  __INDEX_NOTES__
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
<link rel="canonical" href="__CANONICAL__">
<link rel="icon" type="image/svg+xml" href="../favicon.svg">
__THEME_INIT__
<style>
__SHARED_STYLES__
  .console-card { background: var(--panel); border: 1px solid var(--border); border-radius: 10px;
    margin-bottom: 12px; overflow: hidden; }
  .console-card > summary { cursor: pointer; padding: 14px 40px 14px 16px; position: relative;
    display: flex; align-items: center; justify-content: space-between; gap: 12px;
    list-style: none; font-size: 15px; font-weight: 600; user-select: none; }
  .console-card > summary::-webkit-details-marker { display: none; }
  .console-card > summary::after { content: "\25BE"; color: var(--muted);
    transition: transform 0.15s; position: absolute; right: 16px; top: 50%;
    transform: translateY(-50%); }
  .console-card[open] > summary::after { transform: translateY(-50%) rotate(180deg); }
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
  .table-wrap { overflow-x: auto; }
  thead th:first-child { width: 260px; min-width: 260px; }
  thead th:nth-child(5), thead th:nth-child(6) { min-width: 230px; }
  thead th:nth-child(7) { min-width: 380px; }
  .hash { font-family: var(--mono); font-size: 12.5px; color: var(--hash-text);
    white-space: nowrap; display: inline-flex; align-items: center; gap: 6px; }
  .hash button { background: transparent; border: 1px solid var(--border); color: var(--muted);
    border-radius: 6px; padding: 2px 6px; font-size: 11px; cursor: pointer; transition: 0.15s; }
  .hash button:hover { color: var(--accent); border-color: var(--accent-dim); }
  .hash button.copied { color: var(--success); border-color: var(--success); }
  .empty { color: var(--muted); font-style: italic; }
  .region-tag { display: inline-block; background: var(--panel-2); padding: 2px 8px;
    border-radius: 999px; font-size: 12px; color: var(--muted); border: 1px solid var(--border); }
  .size { font-family: var(--mono); font-size: 12.5px; color: var(--hash-text); white-space: nowrap; }
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
  __THEME_TOGGLE__
  <div class="container">
    <div>
      <div class="crumbs"><a href="../index.html">← All manufacturers</a></div>
      <h1>__MFR_NAME__</h1>
      <p>__SUMMARY__</p>
    </div>
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
  __MFR_NOTES__
</div>
<footer>
  Edit <a href="__REPO_URL__/blob/main/data/__MFR_SLUG__.json"><code>data/__MFR_SLUG__.json</code></a> via pull request to contribute.__MFR_NOTES_LINK__
</footer>

<script>
const DATA = __DATA__;
const CONSOLE_NOTES = __CONSOLE_NOTES__;

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
  const notesHtml = CONSOLE_NOTES[g.longName]
    ? `<div class="console-notes">${CONSOLE_NOTES[g.longName]}</div>`
    : "";
  return `<details class="console-card" data-key="${escapeHtml(g.key)}"${isOpen ? " open" : ""}>
    <summary>
      <span>${title}</span>
      <span class="console-meta">${rows.length} BIOS${rows.length === 1 ? "" : "es"}</span>
    </summary>
    <div class="table-wrap"><table>
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
    </table></div>
    ${notesHtml}
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


def to_script_json(obj) -> str:
    """json.dumps, but safe to embed inside a <script> tag (guards against a
    literal '</script>' in string data ending the block early)."""
    return json.dumps(obj, ensure_ascii=False).replace("</", "<\\/")


def write_sitemap(manufacturers):
    slugs = [slugify(doc["manufacturer"]) for doc in manufacturers]
    urls = [f"{SITE_URL}/"] + [f"{SITE_URL}/m/{s}.html" for s in slugs]
    lines = ['<?xml version="1.0" encoding="UTF-8"?>',
             '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">']
    for i, url in enumerate(urls):
        priority = "1.0" if i == 0 else "0.8"
        lines += [
            "  <url>",
            f"    <loc>{url}</loc>",
            f"    <priority>{priority}</priority>",
            "    <changefreq>weekly</changefreq>",
            "  </url>",
        ]
    lines.append("</urlset>")
    (ROOT / "sitemap.xml").write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_robots_txt():
    (ROOT / "robots.txt").write_text(
        f"User-agent: *\nAllow: /\nSitemap: {SITE_URL}/sitemap.xml\n",
        encoding="utf-8",
    )


def write_index(index_payload):
    payload = to_script_json(index_payload)
    index_notes = load_index_notes()
    index_notes_html = f'<div class="page-notes">{index_notes}</div>' if index_notes else ""
    html_out = (INDEX_TEMPLATE
                .replace("__CANONICAL__", f"{SITE_URL}/")
                .replace("__SHARED_STYLES__", SHARED_STYLES)
                .replace("__THEME_INIT__", THEME_INIT_SCRIPT)
                .replace("__THEME_TOGGLE__", THEME_TOGGLE_HTML)
                .replace("__MANUFACTURERS__", payload)
                .replace("__INDEX_NOTES__", index_notes_html))
    OUTPUT_INDEX.write_text(html_out, encoding="utf-8")


def write_manufacturer_page(doc):
    rows = flatten_manufacturer(doc)
    slug = slugify(doc["manufacturer"])
    console_count = len({r["longName"] for r in rows}) or len(doc["consoles"])
    summary = (f"{len(rows)} BIOS entr{'y' if len(rows) == 1 else 'ies'} "
               f"across {console_count} console{'' if console_count == 1 else 's'}.")
    payload = to_script_json(rows)

    mfr_notes = load_manufacturer_notes(slug)
    mfr_notes_html = f'<div class="page-notes">{mfr_notes}</div>' if mfr_notes else ""
    notes_file_exists = (NOTES_DIR / f"{slug}.md").exists()
    mfr_notes_link = (
        f' &middot; <a href="{REPO_URL}/blob/main/notes/{slug}.md"><code>notes/{slug}.md</code></a>'
        if notes_file_exists else ""
    )

    console_notes = {}
    for console in doc["consoles"]:
        html = load_console_notes(slug, console["longName"])
        if html:
            console_notes[console["longName"]] = html
    console_notes_payload = to_script_json(console_notes)

    html_out = (MFR_TEMPLATE
                .replace("__CANONICAL__", f"{SITE_URL}/m/{slug}.html")
                .replace("__SHARED_STYLES__", SHARED_STYLES)
                .replace("__THEME_INIT__", THEME_INIT_SCRIPT)
                .replace("__THEME_TOGGLE__", THEME_TOGGLE_HTML)
                .replace("__MFR_NAME__", doc["manufacturer"])
                .replace("__MFR_SLUG__", slug)
                .replace("__REPO_URL__", REPO_URL)
                .replace("__SUMMARY__", summary)
                .replace("__MFR_NOTES__", mfr_notes_html)
                .replace("__MFR_NOTES_LINK__", mfr_notes_link)
                .replace("__DATA__", payload)
                .replace("__CONSOLE_NOTES__", console_notes_payload))
    (MFR_DIR / f"{slug}.html").write_text(html_out, encoding="utf-8")


def main():
    manufacturers = load_manufacturers()

    if MFR_DIR.exists():
        shutil.rmtree(MFR_DIR)
    MFR_DIR.mkdir(parents=True)

    write_index(build_index_payload(manufacturers))
    for doc in manufacturers:
        write_manufacturer_page(doc)
    write_sitemap(manufacturers)
    write_robots_txt()

    total_entries = sum(
        len(c.get("bioses", []))
        for doc in manufacturers
        for c in doc["consoles"]
    )
    print(f"Wrote index.html + {len(manufacturers)} manufacturer page(s) "
          f"({total_entries} BIOS entries total)")


if __name__ == "__main__":
    main()
