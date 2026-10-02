# run.py
"""Zero-install launcher:  python run.py [config/default.yaml]"""

import logging
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "src"))

from cda.pipeline.main import main  # noqa: E402

if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s   %(levelname)-7s  %(message)s",
        datefmt="%H:%M:%S",
    )
    main(sys.argv[1] if len(sys.argv) > 1 else "config/default.yaml")
