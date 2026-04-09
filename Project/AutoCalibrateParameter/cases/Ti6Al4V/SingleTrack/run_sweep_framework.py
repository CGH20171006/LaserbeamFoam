#!/usr/bin/env python3
import sys
import shutil
import glob
import numpy as np
from pathlib import Path

# Add src to path
project_root = Path(__file__).resolve().parents[3]
src_path = project_root / 'src'
if str(src_path) not in sys.path:
    sys.path.insert(0, str(src_path))

from PyMeltpoolCalib.config.base_config import BaseConfig
from PyMeltpoolCalib.simulation.simulation_runner import SimulationRunner

def custom_archive(power, dest_root):
    """Archiving ALL time steps as requested by user."""
    dest_dir = dest_root / f"{int(power)}W"
    if dest_dir.exists():
        shutil.rmtree(dest_dir)
    dest_dir.mkdir(parents=True, exist_ok=True)
    
    print(f"--> Archiving ALL results to {dest_dir}...")
    
    case_dir = Path.cwd()
    
    # 1. Copy time directories (all numbers)
    for p in case_dir.iterdir():
        if p.is_dir() and p.name.replace('.', '', 1).isdigit(): # simple check for number
             # Skip processor dirs
             shutil.copytree(p, dest_dir / p.name)
             
    # 2. Copy logs and CSVs
    for p in case_dir.glob("log.*"):
        shutil.copy(p, dest_dir)
    for p in case_dir.glob("*.csv"):
        shutil.copy(p, dest_dir)
        
    # 3. Copy constant/system
    shutil.copytree(case_dir / "constant", dest_dir / "constant")
    shutil.copytree(case_dir / "system", dest_dir / "system")
    
    print(f"--> Archived {power}W successfully.")

def main():
    # 1. Setup Config
    # We fix all parameters to Ti6Al4V values
    fixed_values = {
        "sigma": 1.50,
        "marangoni": -2.6e-4,
        "substrate_temp": 300.0,
        "absorptivity": 0.35,
        "recoilCoeff": 1
    }
    
    config = BaseConfig(
        case_dir=Path.cwd(),
        active_params=[], # No optimization, just sweep
        fixed_values=fixed_values,
        # Ensure we have enough cores
        n_proc=24,
        # Don't let it auto-archive to 'runs' folder, we verify archiving manually
        runs_root=Path.cwd() / "results_sweep_framework"
    )

    # 2. Init Runner
    runner = SimulationRunner(config)
    
    # 3. Define Sweep
    powers = [140.0, 200.0, 260.0]
    
    # 4. Callback for archiving
    archive_root = config.runs_root
    
    def on_complete(idx, power, preds):
        print(f"Callback: Finished {power}W. Archiving...")
        custom_archive(power, archive_root)

    # 5. Run
    # params is empty because active_params is empty
    print("Starting Sweep with Framework...")
    print(f"Fixed Parameters: {fixed_values}")
    
    try:
        results = runner.run(
            params=[], 
            power_points=powers, 
            on_power_complete=on_complete,
            job_id=None # Disable internal partial archiving
        )
        print("\nAll Done!")
        print("Results (W, D, A):")
        print(results)
    except Exception as e:
        print(f"Sweep failed: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
