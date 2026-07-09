# trafilatura-scrape

Firecrawl-compatible web scrape server backed by trafilatura.
Speaks the `/v1/scrape` REST API so AI agents can use it as a web extraction backend via `FIRECRAWL_API_URL`.

- Pure Python, `pip install` and run
- Stateless — no storage
- Self-hosted

## Usage

```bash
pip install trafilatura-scrape
trafilatura-scrape                            # default: 127.0.0.1:8766
SCRAPE_PORT=9999 trafilatura-scrape           # custom port
python -m trafilatura_scrape                  # via module
```

### Test it

```bash
curl http://127.0.0.1:8766/health
curl -X POST http://127.0.0.1:8766/v1/scrape \
  -H "Content-Type: application/json" \
  -d '{"url": "https://example.com", "formats": ["markdown"]}'
```

### With Hermes Agent

Add `FIRECRAWL_API_URL=http://127.0.0.1:8766` to the Hermes `.env`.
The `web_extract` tool routes through this server automatically.

## API

### `POST /v1/scrape`

**Request:**
```json
{"url": "https://example.com", "formats": ["markdown"]}
```

**Response:**
```json
{
  "success": true,
  "data": {
    "markdown": "# Markdown content...",
    "html": "<h1>HTML content...</h1>",
    "metadata": {"title": "Page Title", "sourceURL": "https://example.com"}
  }
}
```

### `GET /health`

Returns `{"status": "ok", "service": "trafilatura-scrape"}`.

## How it works

1. Receives a Firecrawl-compatible scrape request
2. Fetches the URL with browser-like headers via `requests`
3. Extracts content using `trafilatura`
4. Returns Firecrawl-shaped JSON

## Nix

```bash
nix build   # uses flake.nix
```

---

*This software was written by an AI and is maintained by an AI.*
