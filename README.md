# trafilatura-scrape

A Firecrawl-compatible web scrape server backed by trafilatura.

Speaks the Firecrawl `/v1/scrape` REST API so AI agents (Hermes, etc.)
can use it as a drop-in web extraction backend via `FIRECRAWL_API_URL`.

## Why

- **No Docker** — pure Python, `pip install` and run
- **No database** — stateless, no storage
- **Self-hosted** — everything runs on your machine
- **Works with Hermes** — set `FIRECRAWL_API_URL` and the native `web_extract`
  tool routes through this server automatically

## Usage

```bash
# Install
pip install trafilatura-scrape

# Run (default: 127.0.0.1:8766)
trafilatura-scrape

# Custom port
SCRAPE_PORT=9999 trafilatura-scrape

# Via Python
python -m trafilatura_scrape --port 9000
```

### Test it

```bash
curl http://127.0.0.1:8766/health

curl -X POST http://127.0.0.1:8766/v1/scrape \
  -H "Content-Type: application/json" \
  -d '{"url": "https://example.com", "formats": ["markdown"]}'
```

### With Hermes Agent

Add to `/data/.hermes/.env`:

```
FIRECRAWL_API_URL=http://127.0.0.1:8766
```

The `web_extract` tool will automatically route through this server.

## API

### `POST /v1/scrape`

Firecrawl-compatible scrape endpoint.

**Request:**
```json
{
  "url": "https://example.com",
  "formats": ["markdown"]
}
```

**Response:**
```json
{
  "success": true,
  "data": {
    "markdown": "# Markdown content...",
    "html": "<h1>HTML content...</h1>",
    "metadata": {
      "title": "Page Title",
      "sourceURL": "https://example.com"
    }
  }
}
```

### `GET /health`

Health check — returns `{"status": "ok", "service": "trafilatura-scrape"}`.

## How it works

1. Receives a Firecrawl-compatible scrape request
2. Fetches the URL with browser-like headers via `requests`
3. Extracts clean content using `trafilatura` (based on readability algorithms)
4. Returns the result in Firecrawl's response format

## Nix

```bash
nix build   # uses flake.nix
```
