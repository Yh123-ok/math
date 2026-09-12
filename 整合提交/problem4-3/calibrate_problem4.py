from pathlib import Path
import sys

CORE_DIR = Path(__file__).resolve().parents[1]
if str(CORE_DIR) not in sys.path:
    sys.path.insert(0, str(CORE_DIR))

from calibrate_common import run

if __name__ == "__main__":
    run(Path(__file__).resolve().parent, 4)
