#问题四-3绘图入口：调用共享绘图核心
from pathlib import Path
import sys

CORE_DIR = Path(__file__).resolve().parents[1]
if str(CORE_DIR) not in sys.path:
    sys.path.insert(0, str(CORE_DIR))

import plot_common as core

if __name__ == "__main__":
    core.main(Path(__file__).resolve().parent, 4)
