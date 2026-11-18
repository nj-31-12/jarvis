"""Start:  python3 -m gta_studio            → http://127.0.0.1:8777
        python3 -m gta_studio --port 8800 --data data/gta_studio.db
"""
from __future__ import annotations

import argparse
from pathlib import Path

from .server import serve


def main() -> None:
    ap = argparse.ArgumentParser(prog="gta_studio", description="GTA TikTok Studio (lokal)")
    ap.add_argument("--port", type=int, default=8777)
    ap.add_argument("--data", default=str(Path("data") / "gta_studio.db"), help="Pfad zur Datenbank")
    args = ap.parse_args()
    serve(Path(args.data), args.port)


if __name__ == "__main__":
    main()
