"""Run the API locally.

    python -m flywire_api.run                # http://127.0.0.1:8000
    python -m flywire_api.run --reload       # reload on edit, for development
    flywire-api --port 9000                  # installed console script

Equivalent, if you prefer driving uvicorn yourself::

    uvicorn flywire_api.app:app --reload

Once it is up:

* Swagger UI:  http://127.0.0.1:8000/docs
* ReDoc:       http://127.0.0.1:8000/redoc
* OpenAPI:     http://127.0.0.1:8000/openapi.json
* WebSocket:   ws://127.0.0.1:8000/ws/simulate
"""

from __future__ import annotations

import argparse
import os

import uvicorn

from .deps import DEFAULT_MAX_CONCURRENT_SIMULATIONS


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m flywire_api.run",
        description=__doc__.splitlines()[0],
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument(
        "--reload",
        action="store_true",
        help="Restart on source changes. Development only.",
    )
    parser.add_argument(
        "--max-concurrent-simulations",
        type=int,
        default=DEFAULT_MAX_CONCURRENT_SIMULATIONS,
        help="Runs allowed in flight before new ones get a 503.",
    )
    parser.add_argument("--log-level", default="info")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)

    # An import string (not an app object) is what --reload needs, and
    # create_app reads its configuration from the environment for exactly that
    # reason -- see flywire_api.app.create_app.
    os.environ["FLYWIRE_API_MAX_CONCURRENT"] = str(args.max_concurrent_simulations)
    uvicorn.run(
        "flywire_api.app:app",
        host=args.host,
        port=args.port,
        reload=args.reload,
        log_level=args.log_level,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
