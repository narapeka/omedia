from __future__ import annotations

import argparse
import os
from collections.abc import Sequence


DEFAULT_PORT = 7108


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="omedia-server", description="Run the OMEDIA production web service")
    parser.add_argument("--host", default=os.environ.get("OMEDIA_HOST", "127.0.0.1"))
    parser.add_argument("--port", type=int, default=_env_port())
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    import uvicorn

    from app.main import create_app

    uvicorn.run(
        create_app(),
        host=args.host,
        port=args.port,
        log_level="info",
    )
    return 0


def _env_port() -> int:
    raw_port = os.environ.get("OMEDIA_PORT")
    if raw_port is None:
        return DEFAULT_PORT
    try:
        return int(raw_port)
    except ValueError as exc:
        raise SystemExit(f"OMEDIA_PORT must be an integer: {raw_port}") from exc


if __name__ == "__main__":
    raise SystemExit(main())
