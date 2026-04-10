#!/usr/bin/env python3
"""
Case-specific entry point for 316L Single Track Calibration.
This wrapper sets up the environment and calls the shared core logic.
"""
import sys
from pathlib import Path

# Add applications/scripts to Python path so we can import AutoCalibrateParameter
# Structure: LaserbeamFoam/Project/AutoCalibrateParameter/316L/SingleTrack/main.py
repo_root = Path(__file__).resolve().parents[4]  # -> LaserbeamFoam
scripts_path = repo_root / 'applications' / 'scripts'
if str(scripts_path) not in sys.path:
    sys.path.insert(0, str(scripts_path))

print("Loading AutoCalibrateParameter…", flush=True)
try:
    from AutoCalibrateParameter.run_cli import main
except ImportError as e:
    print(f"Error: Could not import AutoCalibrateParameter from {scripts_path}")
    print(f"Details: {e}")
    sys.exit(1)

if __name__ == "__main__":
    # Execute the shared main function
    sys.exit(main())
