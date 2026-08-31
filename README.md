# trafilatura-scrape

Firecrawl v2-compatible web scrape server backed by trafilatura.
Speaks the `/v2/scrape` REST API (and keeps `/v1/scrape` for compatibility) so AI agents can use it as a web extraction backend via `FIRECRAWL_API_URL`.

- Pure Python, `pip install` and run
- Stateless — no storage, no browser, no LLM
- Self-hosted

## Usage

```bash
pip install trafilatura-scrape
trafilatura-scrape                            # default: 127.0.0.1:8766
SEARXNG_URL=https://search.example.com trafilatura-scrape   # enable /search
python -m trafilatura_scrape                  # via module
```

### Environment variables

| Variable | Default | Purpose |
|---|---|---|
| `SCRAPE_HOST` | `127.0.0.1` | Bind address |
| `SCRAPE_PORT` | `8766` | Bind port |
| `SEARXNG_URL` | unset | SearXNG instance for `/v1/search` and `/v2/search` (required; search returns 503 without it) |
| `SCRAPE_LANG` | `en` | SearXNG `language` parameter |
| `SCRAPE_MAX_WORKERS` | `4` | Threads for batch scrape |

### Test it

```bash
curl http://127.0.0.1:8766/health
curl -X POST http://127.0.0.1:8766/v2/scrape \
  -H "Content-Type: application/json" \
  -d '{"url": "https://example.com", "formats": ["markdown"]}'
```

### With Hermes Agent

Add `FIRECRAWL_API_URL=http://127.0.0.1:8766` to the Hermes `.env`.
The `web_extract` tool routes through this server automatically.

## API

| Method | Path | Purpose |
|---|---|---|
| GET | `/health` | Liveness check |
| POST | `/v1/scrape` | Scrape a page (v1 compat alias of `/v2/scrape`) |
| POST | `/v2/scrape` | Scrape a page (PDF URLs auto-route to `/v2/parse`) |
| POST | `/v2/batch/scrape` | Scrape up to 50 URLs concurrently |
| POST | `/v2/map` | List URLs for a site (sitemap + page links) |
| POST | `/v2/parse` | Extract PDF text |
| POST | `/v2/search` | SearXNG web/news search, optional inline scrape |
| POST | `/v1/search` | Search, v1 (bare array) response shape |

### `POST /v2/scrape` (and `/v1/scrape`)

**Request:**
```json
{"url": "https://example.com", "formats": ["markdown", "links"]}
```

**Response:**
```json
{
  "success": true,
  "data": {
    "markdown": "# Markdown content...",
    "links": {"internal": ["https://example.com/about"], "external": []},
    "warning": "Skipping unsupported format(s): screenshot",
    "metadata": {
      "title": "Page Title",
      "sourceURL": "https://example.com",
      "statusCode": 200,
      "contentType": "text/html"
    }
  }
}
```

PDF URLs (Content-Type `application/pdf` or `.pdf` suffix) are auto-detected and parsed with `pypdf`; the response is markdown text plus `metadata.numPages`.

### `POST /v2/search` (and `/v1/search`, `GET ?q=`)

**Request:**
```json
{"query": "example", "limit": 5, "offset": 0, "sources": ["web", "news"],
 "scrapeOptions": {"formats": ["markdown"]}}
```

**Response (v2 shape):**
```json
{
  "success": true,
  "data": {
    "web": [{"url": "...", "title": "...", "description": "...", "position": 1}],
    "news": [{"url": "...", "title": "...", "snippet": "...", "date": "...", "position": 1}]
  }
}
```

`/v1/search` returns `{"success": true, "data": [<bare array of results>]}`.
`scrapeOptions` inline-scrapes the top 5 results (markdown only).

### `POST /v2/batch/scrape`

**Request:**
```json
{"urls": ["https://example.com", "https://example.org"], "formats": ["markdown"]}
```

**Response:** `data` is one document (or error document) per URL, order preserved.
```json
{
  "success": true,
  "status": "completed",
  "completed": 2,
  "total": 2,
  "data": [{"success": true, "data": {"markdown": "...", "metadata": {}}}]
}
```

### `POST /v2/map`

**Request:**
```json
{"url": "https://example.com", "limit": 100, "includeSubdomains": false, "search": "about"}
```

**Response:** robots.txt-discovered `sitemap.xml` links plus page links, same-origin and deduped.
```json
{"success": true, "links": [{"url": "https://example.com/about"}]}
```

### `POST /v2/parse`

**Request:** `{"url": "https://example.com/paper.pdf"}`

**Response:** full PDF text (via `pypdf`, text layer only — no OCR) as markdown plus `metadata.numPages`.

### `GET /health`

Returns `{"status": "ok", "service": "trafilatura-scrape"}`.

## Supported formats

`formats` is a list; only the supported subset appears in the response.

| Format | Support |
|---|---|
| `markdown` | Trafilatura extraction |
| `html` | Trafilatura extraction |
| `rawHtml` | Raw response body |
| `links` | `{internal: [...], external: [...]}` |
| `images` | Image URL list |
| `summary` | Extractive first ~200 chars (not LLM) |
| `screenshot`, `json`, `changeTracking`, `query`, `branding`, `product`, ... | Skipped; a `warning` string names them |

## Not supported (deliberate)

- **Screenshots / browser actions** — no headless browser; requests only.
- **LLM formats (`json`, `query`, `branding`, `product`)** — no LLM; reported via `warning`.
- **`changeTracking`** — stateless, no storage to diff against.
- **`/v2/crawl`, async job endpoints (`/v2/batch/scrape/...`)** — synchronous only, no job store.
- **`/v2/extract`, `/v2/agent`** — out of scope.
- **Multipart `/parse` upload** — PDFs are fetched by URL only.
- **PDF OCR** — text layer only.

## Search backend (SearXNG)

`/v1/search` and `/v2/search` require a SearXNG instance with the `format=json` output enabled. Self-hosting is recommended; public instances rate-limit JSON access.

```bash
SEARXNG_URL=https://search.example.com trafilatura-scrape
```

Without `SEARXNG_URL`, search endpoints return 503 with a clear error. `SCRAPE_LANG` sets the SearXNG `language` parameter.

## How it works

1. Receives a Firecrawl-compatible request
2. Fetches the URL with browser-like headers via `requests`
3. Extracts content using `trafilatura` (PDFs via `pypdf`, search via SearXNG)
4. Returns Firecrawl v2-shaped JSON

## Nix

```bash
nix build   # uses flake.nix
```

---

*This software was written by an AI and is maintained by an AI.*
