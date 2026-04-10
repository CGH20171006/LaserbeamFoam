# MeltPool Calibration Project

## Project Structure

- **`applications/scripts/AutoCalibrateParameter/`**: Core Python calibration library (at repo root level).
  - Contains config, optimizers, simulation runners, postprocessing modules.

- **Material case directories** (in this folder):
  - `316L/SingleTrack`: Single track laser melting calibration for 316L stainless steel.
  - `316L/MultiTrack`: (Planned) Multi-track calibration.
  - `Ti6Al4V/SingleTrack`: Single track calibration for Ti-6Al-4V.

## Usage

To run the calibration for 316L Single Track:

1. Navigate to the case directory:
   ```bash
   cd 316L/SingleTrack
   ```

2. Run the calibration script:
   ```bash
   python main.py
   ```
   (The script will automatically detect `config.yaml` in the current directory)

## Requirements

- OpenFOAM (v2506 or compatible)
- Python 3.8+
- Scikit-optimize
- NumPy, Pandas, Scipy

## Collaboration

For collaborators who already have a `LaserbeamFoam` source tree and need to reproduce the same solver behavior and calibration workflow, see [`COLLABORATION_SETUP.md`](/home/cgh/LaserbeamFoam/Project/COLLABORATION_SETUP.md).
