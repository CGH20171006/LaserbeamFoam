#!/usr/bin/env pvpython
"""
Batch visualization script for OpenFOAM meltpool results.
Automatically creates symlinks to constant/ and system/ directories.

Usage:
    pvpython visualize_meltpool.py
"""

import os
import sys
from pathlib import Path

try:
    from paraview.simple import *
except ImportError:
    print("ERROR: This script must be run with pvpython")
    sys.exit(1)


def setup_case_links(run_dir, base_dir):
    """Create symlinks to constant/ and system/ if they don't exist."""
    run_dir = Path(run_dir)
    base_dir = Path(base_dir)

    constant_link = run_dir / "constant"
    system_link = run_dir / "system"

    if not constant_link.exists():
        os.symlink(base_dir / "constant", constant_link, target_is_directory=True)

    if not system_link.exists():
        os.symlink(base_dir / "system", system_link, target_is_directory=True)


def visualize_case(case_dir, output_file, field='meltHistory', time_val=0.00034):
    """Visualize a single case and save screenshot."""
    case_dir = Path(case_dir)

    # Create .foam file
    foam_file = case_dir / f"{case_dir.name}.foam"
    foam_file.touch(exist_ok=True)

    print(f"  Processing: {case_dir.name}")

    try:
        # Load case
        reader = OpenFOAMReader(FileName=str(foam_file))
        reader.MeshRegions = ['internalMesh']
        reader.CellArrays = [field, 'alpha.metal', 'T']
        reader.UpdatePipeline()

        # Set time
        if reader.TimestepValues:
            closest_time = min(reader.TimestepValues, key=lambda x: abs(x - time_val))
            GetAnimationScene().AnimationTime = closest_time

        # Apply threshold (show only metal region)
        threshold = Threshold(Input=reader)
        threshold.Scalars = ['CELLS', 'alpha.metal']
        # ParaView 5.10+ API
        threshold.LowerThreshold = 0.5
        threshold.UpperThreshold = 1.0
        threshold.ThresholdMethod = 'Between'
        threshold.UpdatePipeline()

        # Apply Slice filter along Y axis at Y=0.0004
        slice_filter = Slice(Input=threshold)
        slice_filter.SliceType = 'Plane'
        slice_filter.SliceType.Origin = [0.0, 0.0004, 0.0]
        slice_filter.SliceType.Normal = [0.0, 1.0, 0.0]  # Y-axis normal
        slice_filter.UpdatePipeline()

        # Create view
        view = CreateView('RenderView')
        view.ViewSize = [1920, 1080]
        view.UseColorPaletteForBackground = 0  # Disable palette override
        view.Background = [1, 1, 1]  # White background

        # Display
        display = Show(slice_filter, view)
        ColorBy(display, ('CELLS', field))

        # Color map with range 0-1
        lut = GetColorTransferFunction(field)
        lut.ApplyPreset('Rainbow Desaturated', True)
        lut.RescaleTransferFunction(0.0, 1.0)  # Set range to 0-1
        display.SetScalarBarVisibility(view, True)

        # Set camera to view XZ plane (looking along Y axis)
        view.CameraPosition = [0.0, 0.01, 0.0]  # Camera position (looking from +Y)
        view.CameraFocalPoint = [0.0, 0.0004, 0.0]  # Looking at slice
        view.CameraViewUp = [0.0, 0.0, 1.0]  # Z is up
        view.ResetCamera()

        # Save
        output_file = Path(output_file)
        output_file.parent.mkdir(parents=True, exist_ok=True)
        SaveScreenshot(str(output_file), view, ImageResolution=[1920, 1080])
        print(f"    ✓ Saved: {output_file.name}")

        # Cleanup
        Delete(display)
        Delete(slice_filter)
        Delete(threshold)
        Delete(reader)
        Delete(view)

        return True

    except Exception as e:
        print(f"    ✗ Error: {e}")
        return False


def main():
    base_dir = Path(__file__).parent
    runs_dir = base_dir / "runs"
    output_dir = base_dir / "visualization_output"

    print("="*80)
    print("OpenFOAM Meltpool Batch Visualization")
    print("="*80)
    print(f"Base directory: {base_dir}")
    print(f"Output directory: {output_dir}")
    print()

    # Find all cases
    cases = []
    for run_id_dir in sorted(runs_dir.iterdir()):
        if not run_id_dir.is_dir() or not run_id_dir.name.isdigit():
            continue

        for power_dir in sorted(run_id_dir.iterdir()):
            if not power_dir.is_dir():
                continue

            time_dir = power_dir / "0.00034"
            if time_dir.exists() and (time_dir / "meltHistory").exists():
                cases.append({
                    'path': power_dir,
                    'run_id': run_id_dir.name,
                    'power': power_dir.name
                })

    print(f"Found {len(cases)} cases to process\n")

    if not cases:
        print("No cases found!")
        return

    # Process each case
    success = 0
    for i, case in enumerate(cases, 1):
        print(f"[{i}/{len(cases)}] Run {case['run_id']}, Power {case['power']}")

        # Setup symlinks
        setup_case_links(case['path'], base_dir)

        # Output file
        output_file = output_dir / case['run_id'] / f"{case['power']}_meltHistory.png"

        if visualize_case(case['path'], output_file):
            success += 1
        print()

    print("="*80)
    print(f"Complete! Successfully processed {success}/{len(cases)} cases")
    print(f"Output saved to: {output_dir}")
    print("="*80)


if __name__ == '__main__':
    main()
