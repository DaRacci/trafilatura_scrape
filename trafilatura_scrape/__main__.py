"""Entry point — run with ``python -m trafilatura_scrape`` or ``trafilatura-scrape``."""

import sys

from trafilatura_scrape.server import serve


def main() -> None:
    """Parse CLI args and start the server."""
    if "--version" in sys.argv or "-V" in sys.argv:
        from trafilatura_scrape import __version__
        print(f"trafilatura-scrape {__version__}")
        sys.exit(0)

    if "--help" in sys.argv or "-h" in sys.argv:
        print("Usage: trafilatura-scrape [OPTIONS]")
        print()
        print("Firecrawl-compatible scrape server backed by trafilatura.")
        print()
        print("Options:")
        print("  --host HOST    Address to bind (default: 127.0.0.1)")
        print("  --port PORT    Port to listen on  (default: 8766)")
        print("  -V, --version  Show version and exit")
        print("  -h, --help     Show this help and exit")
        print()
        print("Env overrides:")
        print("  SCRAPE_HOST    (default: 127.0.0.1)")
        print("  SCRAPE_PORT    (default: 8766)")
        sys.exit(0)

    serve()


if __name__ == "__main__":
    main()
