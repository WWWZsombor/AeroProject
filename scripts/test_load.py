# scripts/test_load.py
"""
Quick test:  config/default.yaml  →  process all JSON  →  plot segments.
"""

import logging
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from cda.pipeline.main import main

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s   %(levelname)-7s  %(message)s",
)

if __name__ == "__main__":
    yaml = os.path.join(
        os.path.dirname(__file__), "..", "config", "default.yaml"
     )
    written = main(yaml_path=yaml)
    print(f"\n{len(written)} file(s) written.")
    for p in written:
        print(f"  {p}")
