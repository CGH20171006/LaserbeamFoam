"""Parse Abaqus .dat and extract time, S33, E33.

Behavior matches the MATLAB Read_Dat_S33_E33.m logic you shared:
- Track current_time from lines containing 'TOTAL TIME COMPLETED' (take last number).
- Treat a numeric line with >= 4 columns as a candidate data row.
- Default filter: element=1 and intPt=1 (first two numbers in the row).
- Column mapping: col3 -> S33, col4 -> E33

If your model uses different element / integration point IDs, change ELEMENT_ID / INTPT_ID.
"""

from __future__ import annotations

import re
import time
from pathlib import Path
from typing import Tuple

import numpy as np

# Default target (match your MATLAB code)
ELEMENT_ID = 1
INTPT_ID = 1

_NUM_RE = re.compile(r"[+-]?(?:\d+\.?\d*|\.\d+)(?:[eEdD][+-]?\d+)?")


def read_dat_s33_e33(job_name: str, cwd: Path | str = ".", timeout: int = 30) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Return (time, stress_S33, strain_E33) as numpy arrays.

    Parameters
    ----------
    job_name : str
        Abaqus job name (without extension).
    cwd : Path | str
        Directory containing <job_name>.dat.
    timeout : int
        Seconds to wait for the .dat file to appear.
    """
    cwd = Path(cwd)
    dat_file = cwd / f"{job_name}.dat"

    # Wait for file to appear (Abaqus writes it near the end)
    t0 = time.time()
    while not dat_file.exists():
        time.sleep(1.0)
        if time.time() - t0 > timeout:
            print("Warning: .dat not found (timeout).")  # align with MATLAB 'warn and return empty'
            return np.array([]), np.array([]), np.array([])

    # Small delay to reduce partial-read risk
    time.sleep(1.0)

    time_vec, stress_vec, strain_vec = [], [], []
    current_time = 0.0

    with dat_file.open("r", errors="ignore") as f:
        for line in f:
            if "TOTAL TIME COMPLETED" in line:
                nums = _NUM_RE.findall(line)
                if nums:
                    try:
                        current_time = float(nums[-1])
                    except ValueError:
                        pass
                continue

            if len(line) > 10 and any(ch.isdigit() for ch in line):
                try:
                    arr = np.fromstring(line, sep=" ")
                except ValueError:
                    nums = _NUM_RE.findall(line)
                    if len(nums) < 4:
                        continue
                    try:
                        arr = np.asarray([float(n.replace("D", "E").replace("d", "E")) for n in nums], dtype=float)
                    except ValueError:
                        continue
                if arr.size >= 4:
                    # element / intPt filter
                    if abs(arr[0] - float(ELEMENT_ID)) < 0.1 and abs(arr[1] - float(INTPT_ID)) < 0.1:
                        time_vec.append(current_time)
                        stress_vec.append(float(arr[2]))  # S33
                        strain_vec.append(float(arr[3]))  # E33

    if not time_vec:
        print("Warning: no recognizable data rows in .dat.")
        return np.array([]), np.array([]), np.array([])

    return (np.asarray(time_vec, dtype=float),
            np.asarray(stress_vec, dtype=float),
            np.asarray(strain_vec, dtype=float))
