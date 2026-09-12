"""One-command reproduction of the official Problem 4-2 calculation.

Run from any directory: python 4test/main.py
"""
from experiments.simple_mpc import run
from experiments.finalize_mpc import main as export_workbook
from src.plot_mpc import create_figures
from pathlib import Path
import subprocess
import sys


if __name__=='__main__':
    run()               # Daily causal forecast, locked normal plan, MPC.
    export_workbook()   # Official Excel, CSV, and readback validation.
    create_figures()    # Charts solely from saved CSVs.
    base=Path(__file__).resolve().parent
    for script in ('audit_mpc_information.py','reproduce_mpc_notebook.py',
                   'write_mpc_report.py','write_mpc_manifest.py'):
        subprocess.run([sys.executable,str(base/'tools'/script)],check=True,cwd=base.parent)
