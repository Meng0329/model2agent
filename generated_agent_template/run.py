"""Entrypoint: python3 run.py --port 7860"""
import argparse
import os

import uvicorn


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--port", type=int, default=int(os.getenv("PORT", "7860")))
    p.add_argument("--host", default="0.0.0.0")
    args = p.parse_args()
    uvicorn.run("app:app", host=args.host, port=args.port, log_level="info")


if __name__ == "__main__":
    main()
