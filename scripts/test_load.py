# scripts/test_load.py
"""
Quick test:  point at the YAML, run the pipeline, inspect output.
Change ONLY config/default.yaml to switch test configurations.
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
    # the YAML path is the ONLY thing you may need to change here
    yaml = os.path.join(
        os.path.dirname(__file__), "..", "config", "default.yaml"
    )
    written = main(yaml_path=yaml)

    print(f"\n  {len(written)} CSV file(s) written.")
    print(f"  Folder: {os.path.dirname(written[0]) if written else 'N/A'}")
    for p in written:
        print(f"    {os.path.basename(p)}")
