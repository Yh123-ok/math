#问题三入口：调用共享调度核心
from pathlib import Path
import sys

CORE_DIR = Path(__file__).resolve().parents[1]
if str(CORE_DIR) not in sys.path:
    sys.path.insert(0, str(CORE_DIR))

import dispatch_core


if __name__ == "__main__":
    dispatch_core.main(Path(__file__).resolve().parent, 3)
