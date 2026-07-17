#!/usr/bin/env python3
"""Unified entry point for REagent.

The academic repository layout keeps all runnable workflows behind this file.
Scripts in ``script/`` call this module instead of invoking package internals
directly.
"""
from __future__ import annotations

import argparse
import os
import runpy
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent
SRC_ROOT = PROJECT_ROOT / "src"
REAGENT_MODULE_ROOT = SRC_ROOT / "reagent"


def configure_imports() -> None:
    for path in (SRC_ROOT, REAGENT_MODULE_ROOT):
        value = str(path)
        if value not in sys.path:
            sys.path.insert(0, value)
    os.chdir(PROJECT_ROOT)


def run_cli(args: list[str]) -> None:
    configure_imports()
    from reagent.main import main as reagent_main

    sys.argv = ["reagent.main", *args]
    reagent_main()


def run_server(args: list[str]) -> None:
    configure_imports()
    parser = argparse.ArgumentParser(description="Start the REagent FastAPI server")
    parser.add_argument("--host", default=os.getenv("API_HOST", "0.0.0.0"))
    parser.add_argument("--port", type=int, default=int(os.getenv("API_PORT", "8000")))
    parser.add_argument("--reload", action="store_true")
    parsed = parser.parse_args(args)

    import uvicorn

    uvicorn.run(
        "backend.main:app",
        host=parsed.host,
        port=parsed.port,
        reload=parsed.reload,
    )


def run_smoke(args: list[str]) -> None:
    configure_imports()
    sys.argv = ["script/api_smoke_test.py", *args]
    runpy.run_path(str(PROJECT_ROOT / "script" / "api_smoke_test.py"), run_name="__main__")


def print_usage() -> None:
    print(
        "\n".join([
            "Usage:",
            "  python main.py serve [--host HOST] [--port PORT] [--reload]",
            "  python main.py smoke [quick|pipeline] [options]",
            "  python main.py cli --description_file dataset/requirements/software_analysis.txt [options]",
            "  python main.py --description_file dataset/requirements/software_analysis.txt [options]",
            "",
            "Repository entry rule: scripts in script/ should call this file.",
        ])
    )


def main(argv: list[str] | None = None) -> None:
    argv = list(sys.argv[1:] if argv is None else argv)
    if not argv or argv[0] in ("-h", "--help", "help"):
        print_usage()
        return
    if argv[0].startswith("-"):
        run_cli(argv)
        return

    command, rest = argv[0], argv[1:]
    if command == "cli":
        run_cli(rest)
    elif command == "serve":
        run_server(rest)
    elif command == "smoke":
        run_smoke(rest)
    else:
        run_cli(argv)


if __name__ == "__main__":
    main()
