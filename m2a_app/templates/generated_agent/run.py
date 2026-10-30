"""Entry point for the generated Model Agent. `python3 run.py --port N`."""
import argparse
import os

import app


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--port", type=int, default=int(os.getenv("M2A_PREVIEW_PORT", "7860")))
    a = p.parse_args()
    app.launch(port=a.port)


if __name__ == "__main__":
    main()
