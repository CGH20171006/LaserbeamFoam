# MeltPool Calibration Project

## Project Structure

- **src/**: Core calibration algorithms and simulation drivers.
  - `PyMeltpoolCalib`: Main Python package for calibration.
  - `main.py`: Entry point for running optimizations.

- **cases/**: Simulation scenarios.
  - `316L/SingleTrack`: Single track laser melting calibration for 316L stainless steel.
  - `316L/MultiTrack`: (Planned) Multi-track calibration.

## Usage

To run the calibration for 316L Single Track:

1. Navigate to the case directory:
   ```bash
   cd cases/316L/SingleTrack
   ```

2. Run the calibration script:
   ```bash
   python ../../../src/main.py
   ```
   (The script will automatically detect `config.yaml` in the current directory)

## Requirements

- OpenFOAM (v2506 or compatible)
- Python 3.8+
- Scikit-optimize
- NumPy, Pandas, Scipy

## Collaboration

For collaborators who already have a `LaserbeamFoam` source tree and need to reproduce the same solver behavior and calibration workflow, see [`COLLABORATION_SETUP.md`](/home/cgh/LaserbeamFoam/Project/AutoCalibrateParameter/COLLABORATION_SETUP.md).
