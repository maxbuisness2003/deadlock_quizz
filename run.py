"""Start the Deadlock Quiz site.

    python run.py            # http://127.0.0.1:8001
    python run.py --port 9000
    python run.py --host 0.0.0.0

On hosting platforms (Render, Hugging Face Spaces, Railway) the port and host
are taken from the PORT / HOST environment variables.
"""

from __future__ import annotations

import argparse
import os

import uvicorn


def main() -> None:
    parser = argparse.ArgumentParser(description="Deadlock Quiz")
    parser.add_argument("--host", default=os.environ.get("HOST", "127.0.0.1"))
    parser.add_argument("--port", type=int, default=int(os.environ.get("PORT", "8001")))
    parser.add_argument("--reload", action="store_true")
    args = parser.parse_args()

    print(f"Deadlock Quiz -> http://{args.host}:{args.port}")
    uvicorn.run(
        "app.main:app",
        host=args.host,
        port=args.port,
        reload=args.reload,
        log_level="info",
    )


if __name__ == "__main__":
    main()
