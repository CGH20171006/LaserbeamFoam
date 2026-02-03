#!/usr/bin/env python3
"""
Case-specific entry point for 316L Single Track Calibration.
This wrapper sets up the environment and calls the shared core logic.
"""
import sys
from pathlib import Path

# Add the src directory to the Python path so we can import the core library
# Assumes project structure: root/cases/Material/Case/main.py -> root/src
project_root = Path(__file__).resolve().parents[3]
src_path = project_root / 'src'
if str(src_path) not in sys.path:
    sys.path.insert(0, str(src_path))

try:
    from PyMeltpoolCalib.run_cli import main
except ImportError as e:
    print(f"Error: Could not import PyMeltpoolCalib from {src_path}")
    print(f"Details: {e}")
    sys.exit(1)

if __name__ == "__main__":
    # Execute the shared main function
    sys.exit(main())
