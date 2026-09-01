# trafilatura-scrape

Firecrawl v2-compatible web scrape server backed by trafilatura
and optionally SearxNG.
Speaks the `/v2/scrape` REST API
(and keeps `/v1/scrape` for compatibility)
so AI agents can use it as a web extraction backend
via `FIRECRAWL_API_URL`.

- Pure Python, `pip install` and run
- Stateless, no storage
- Self-hosted

## Usage

```bash
pip install trafilatura-scrape
trafilatura-scrape                            # default: 127.0.0.1:8766
SEARXNG_URL=https://search.example.com trafilatura-scrape   # enable the search endpoints
python -m trafilatura_scrape                  # via module
```

### Environment variables

| Variable | Default | Purpose |
|---|---|---|
| `SCRAPE_HOST` | `127.0.0.1` | Bind address |
| `SCRAPE_PORT` | `8766` | Bind port |
| `SEARXNG_URL` | unset | SearXNG instance for search (required; search returns 503 without it) |
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
| POST | `/v2/scrape` | Scrape a page (PDF URLs parsed automatically) |
| POST | `/v2/batch/scrape` | Scrape up to 50 URLs concurrently |
| POST | `/v2/map` | List URLs for a site (sitemap + page links) |
| POST | `/v2/parse` | Extract PDF text |
| POST | `/v2/search` | SearXNG web/news search, optional inline scrape |
| POST | `/v1/search` | Search, using the v1 format |

### `POST /v{1,2}/scrape`

**Request:**
```json
{"url": "https://example.com", "formats": ["markdown", "links", {"type": "screenshot"}]}
```

**Response:**
```json
{
  "success": true,
  "data": {
    "markdown": "# Markdown content...",
    "links": ["https://example.com/about"],
    "warning": "Formats not supported by this backend: screenshot",
    "metadata": {
      "title": "Page Title",
      "sourceURL": "https://example.com",
      "statusCode": 200,
      "contentType": "text/html"
    }
  }
}
```

PDF URLs are auto-detected and parsed with `pypdf`.

### `POST /v{1,2}/search`

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

`/v1/search` returns `{"success": true, "data": [<results>]}` using the v1 format.
`scrapeOptions` inline-scrapes the top 5 results (markdown only).

### `POST /v2/batch/scrape`

**Request:**
```json
{"urls": ["https://example.com", "https://example.org"], "formats": ["markdown"]}
```

**Response:** `data` is one document (or error document) per URL, order is preserved.
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

**Response:** PDF text as markdown.
OCR is not used.

### `GET /health`

Returns `{"status": "ok", "service": "trafilatura-scrape"}`.

## Supported formats

`formats` is a list; only the supported subset appears in the response.

| Format | Support |
|---|---|
| `markdown` | Trafilatura extraction |
| `html` | Trafilatura extraction |
| `rawHtml` | Raw response body |
| `links` | Flat list of URL strings |
| `images` | Image URL list |
| `summary` | Extractive first ~200 chars |
| `screenshot`, `json`, `changeTracking`, `query`, `branding`, `product`, ... | Skipped; a `warning` string names them |

## Not supported

- Screenshots / browser actions
- LLM assisted formats
- `changeTracking`
- `/v2/crawl` and async job endpoints
- `/v2/extract`, `/v2/agent`
- Multipart `/parse` upload
- PDF OCR

## Search backend (SearXNG)

`/v1/search` and `/v2/search` require a SearXNG instance
with the `format=json` output enabled.
Self-hosting is recommended; public instances rate-limit JSON access.

```bash
SEARXNG_URL=https://search.example.com trafilatura-scrape
```

Without `SEARXNG_URL`, search endpoints return 503 with a clear error.
`SCRAPE_LANG` sets the SearXNG `language` parameter.

## How it works

1. Receives a Firecrawl-compatible request
2. Fetches the URL with browser-like headers via `requests`
3. Extracts content using an appropriate backend
4. Returns Firecrawl v2-shaped JSON

## Nix

```bash
nix build   # uses flake.nix
```

---

*This software was written by an AI and is maintained by an AI.*
