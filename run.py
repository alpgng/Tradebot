"""Web paneli başlatır: python run.py  (varsayılan http://127.0.0.1:8000)

Not: Botlar API süreci içinde thread olarak çalışır; uvicorn'u --workers > 1 ile ÇALIŞTIRMAYIN,
aksi halde her süreç botları ayrı ayrı çalıştırır.
"""
import argparse
import logging

import uvicorn

from tradebot.api import create_app

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8000)
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    uvicorn.run(create_app(), host=args.host, port=args.port, workers=1)
