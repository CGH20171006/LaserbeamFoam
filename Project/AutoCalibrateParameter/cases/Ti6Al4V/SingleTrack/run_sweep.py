import os
import shutil
import subprocess
import glob
import re
import time

# --- Configuration ---
CASE_DIR = os.getcwd()
POWERS = [140.0, 200.0, 260.0]
ARCHIVE_ROOT = os.path.join(CASE_DIR, "results_sweep")
LASER_POWER_FILE = os.path.join(CASE_DIR, "constant/timeVsLaserPower")
N_PROC = 24  # Match system/decomposeParDict

def update_laser_power(power):
    """Updates the laser power in constant/timeVsLaserPower."""
    print(f"--> Updating laser power to {power} W")
    with open(LASER_POWER_FILE, 'r') as f:
        content = f.read()
    
    # Use regex to replace the power value in lines like "(0 200.0)" or "(1e-8 200.0)"
    # We look for lines with 2 numbers and assume the second one is power if it's > 0 originally
    # However, simplest way given the known format is to replace all "200.0" 
    # But to be robust, let's rebuild the specific string content we saw
    
    # Template based on observed file content
    # Note: Using fixed turn-off time at 600e-6 as per original file
    new_content = f"""(
    (0           {power})
    (1e-8           {power})
    (600e-6           {power})
    (600.001e-6           0.0)
    (1000e-6           0.0)
)
"""
    with open(LASER_POWER_FILE, 'w') as f:
        f.write(new_content)

def run_command(cmd, log_file=None):
    """Runs a shell command."""
    print(f"--> Running: {cmd}")
    if log_file:
        with open(log_file, "w") as outfile:
            subprocess.run(cmd, shell=True, check=True, stdout=outfile, stderr=subprocess.STDOUT)
    else:
        subprocess.run(cmd, shell=True, check=True)

def run_simulation(power):
    """Runs the full OpenFOAM simulation chain."""
    print(f"\n=== Starting Simulation for {power} W ===")
    
    # 1. Clean
    print("--> Cleaning case...")
    subprocess.run("./Allclean", shell=True) # Ignore errors
    
    # 2. Pre-processing
    run_command("blockMesh", log_file="log.blockMesh")
    run_command("setSolidFraction", log_file="log.setSolidFraction")
    run_command("decomposePar", log_file="log.decomposePar")
    
    # 3. Solver (Parallel)
    print(f"--> Running laserbeamFoam on {N_PROC} cores...")
    cmd_solver = f"mpirun -np {N_PROC} --oversubscribe laserbeamFoam -parallel"
    try:
        run_command(cmd_solver, log_file="log.laserbeamFoam")
    except subprocess.CalledProcessError:
        print(f"!!! Simulation failed for {power} W. Check log.laserbeamFoam !!!")
        return False
        
    # 4. Reconstruction
    print("--> Reconstructing results...")
    run_command("reconstructPar", log_file="log.reconstructPar")
    
    return True

def archive_results(power):
    """Moves results to archive folder."""
    dest_dir = os.path.join(ARCHIVE_ROOT, f"{power}W")
    if os.path.exists(dest_dir):
        shutil.rmtree(dest_dir)
    os.makedirs(dest_dir)
    
    print(f"--> Archiving results to {dest_dir}...")
    
    # Move time directories (numbers)
    # We look for directories that are numbers or scientific notation
    for item in os.listdir(CASE_DIR):
        if os.path.isdir(item):
            # Check if it looks like a time directory (0, 0.0001, 1e-5, etc)
            if re.match(r'^[0-9.]+(?:e-?[0-9]+)?$', item):
                shutil.move(item, os.path.join(dest_dir, item))
    
    # Copy logs
    for log in glob.glob("log.*"):
        shutil.copy(log, dest_dir)
        
    # Copy constant/system for reference
    shutil.copytree("constant", os.path.join(dest_dir, "constant"))
    shutil.copytree("system", os.path.join(dest_dir, "system"))
    
    # Copy post-processing CSVs if any
    for csv in glob.glob("*.csv"):
        shutil.copy(csv, dest_dir)

    print(f"=== Completed {power} W ===\n")

def main():
    if not os.path.exists(ARCHIVE_ROOT):
        os.makedirs(ARCHIVE_ROOT)
        
    for power in POWERS:
        update_laser_power(power)
        success = run_simulation(power)
        if success:
            archive_results(power)
        else:
            print(f"Skipping archiving for {power}W due to failure.")

if __name__ == "__main__":
    main()
