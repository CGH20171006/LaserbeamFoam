#!/usr/bin/env pvpython
"""
Batch visualization script for OpenFOAM meltpool results using ParaView.
This script automates the process of:
1. Loading OpenFOAM case
2. Applying isoVolume filter
3. Visualizing meltHistory field
4. Saving screenshots or exporting data

Usage:
    pvpython batch_visualize_meltpool.py

Or if pvpython is not in PATH:
    /path/to/paraview/bin/pvpython batch_visualize_meltpool.py
"""

import os
import sys
from pathlib import Path

try:
    from paraview.simple import *
except ImportError:
    print("ERROR: This script must be run with pvpython (ParaView's Python interpreter)")
    print("Usage: pvpython batch_visualize_meltpool.py")
    sys.exit(1)


def process_case(case_path, output_dir, time_value="0.00034"):
    """
    Process a single OpenFOAM case and generate visualization.

    Args:
        case_path: Path to the OpenFOAM case directory
        output_dir: Directory to save output images
        time_value: Time step to visualize (default: 0.00034)
    """
    case_path = Path(case_path)
    case_name = case_path.name

    # Check if the time directory exists
    time_dir = case_path / time_value
    if not time_dir.exists():
        print(f"  ⚠ Time directory {time_value} not found in {case_path}")
        return False

    # Check if meltHistory exists
    melt_history_file = time_dir / "meltHistory"
    if not melt_history_file.exists():
        print(f"  ⚠ meltHistory not found in {time_dir}")
        return False

    print(f"  Processing: {case_path}")

    try:
        # Create a new 'OpenFOAMReader'
        foam_file = case_path / f"{case_path.name}.foam"

        # Create empty .foam file if it doesn't exist
        if not foam_file.exists():
            foam_file.touch()

        reader = OpenFOAMReader(FileName=str(foam_file))

        # Get available fields
        reader.MeshRegions = ['internalMesh']
        reader.CellArrays = ['meltHistory', 'T', 'alpha.metal']

        # Update to read the data
        reader.UpdatePipeline()

        # Set time to the desired value
        available_times = reader.TimestepValues
        if available_times:
            # Find closest time to requested time_value
            target_time = float(time_value)
            closest_time = min(available_times, key=lambda x: abs(x - target_time))
            animationScene = GetAnimationScene()
            animationScene.AnimationTime = closest_time
            print(f"    Set time to: {closest_time}")

        # Apply IsoVolume filter (equivalent to Clip or Threshold)
        # For meltpool visualization, we typically want alpha.metal > 0.5
        threshold = Threshold(Input=reader)
        threshold.Scalars = ['CELLS', 'alpha.metal']
        threshold.ThresholdRange = [0.5, 1.0]
        threshold.UpdatePipeline()

        # Create a render view
        renderView = CreateView('RenderView')
        renderView.ViewSize = [1920, 1080]
        renderView.Background = [1, 1, 1]  # White background

        # Display the threshold
        display = Show(threshold, renderView)

        # Color by meltHistory
        ColorBy(display, ('CELLS', 'meltHistory'))

        # Get color transfer function
        meltHistoryLUT = GetColorTransferFunction('meltHistory')
        meltHistoryLUT.ApplyPreset('Rainbow Desaturated', True)

        # Show color bar
        display.SetScalarBarVisderView, True)

        # Reset camera to fit data
        renderView.ResetCamera()

        # Create output directory if it doesn't exist
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

        # Generate output filename
        output_file = output_dir / f"{case_name}_meltHistory.png"

        # Save screenshot
        SaveScreenshot(str(output_file), renderView, ImageResolution=[1920, 1080])
        print(f"    ✓ Saved: {output_file}")

        # Clean up
        Delete(display)
        Delete(threshold)
        Delete(reader)
        Delete(renderView)

        return True

    except Exception as e:
        print(f"  ✗ Error processing {case_path}: {e}")
        return False


def find_all_cases(base_dir, time_value="0.00034"):
    """
    Find all OpenFOAM cases in the runs directory.

    Args:
        base_dir: Base directory containing runs
        time_value: Time step to look for

    Returns:
        List of case paths
    """
    base_path = Path(base_dir)
    runs_dir = base_path / "runs"

    if not runs_dir.exists():
        print(f"ERROR: runs directory not found: {runs_dir}")
        return []

    cases = []

    # Pattern: runs/<run_id>/<power>W/
    for run_dir in sorted(runs_dir.iterdir()):
        if not run_dir.is_dir() or run_dir.name in ['plots', 'simulations']:
            continue

        for power_dir in sorted(run_dir.iterdir()):
            if not power_dir.is_dir():
                continue

            time_dir = power_dir / time_value
            if time_dir.exists():
                cases.append(power_dir)

    return cases


def main():
    """Main execution function."""

    # Configuration
    base_dir = Path(__file__).parent
    time_value = "0.00034"
    output_dir = base_dir / "visualization_output"

    print("=" * 80)
    print("OpenFOAM Meltpool Batch Visualization Script")
    print("=" * 80)
    print(f"Base directory: {base_dir}")
    print(f"Time value: {time_value}")
    print(f"Output directory: {output_dir}")
    print()

    # Find all cases
    print("Searching for cases...")
    cases = find_all_cases(base_dir, time_value)

    if not cases:
        print("No cases found!")
        return

    print(f"Found {len(cases)} cases to process")
    print()

    # Process each case
    success_count = 0
    for i, case_path in enumerate(cases, 1):
        print(f"[{i}/{len(cases)}] Processing case...")

        # Create subdirectory structure in output
        relative_path = case_path.relative_to(base_dir / "runs")
        case_output_dir = output_dir / relative_path.parent

        if process_case(case_path, case_output_dir, time_value):
            success_count += 1
        print()

    # Summary
    print("=" * 80)
    print(f"Processing complete!")
    print(f"Successfully processed: {success_count}/{len(cases)} c  print(f"Output saved to: {output_dir}")
    print("=" * 80)


if __name__ == "__main__":
    main()
