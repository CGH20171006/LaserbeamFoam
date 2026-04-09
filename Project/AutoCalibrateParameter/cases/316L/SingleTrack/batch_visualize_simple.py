#!/usr/bin/env pvpython
"""
Simple batch visualization script for OpenFOAM meltpool results.

Usage:
    pvpython batch_visualize_simple.py [options]

Options:
    --time VALUE      Time step to visualize (default: 0.00034)
    --field FIELD     Field to visualize (default: meltHistory)
    --output DIR      Output directory (default: ./visualization_output)
    --format FORMAT   Output format: png, jpg, or vtk (default: png)
"""

import os
import sys
import argparse
from pathlib import Path

try:
    from paraview.simple import *
except ImportError:
    print("ERROR: This script must be run with pvpython")
    print("Try: pvpython batch_visualize_simple.py")
    sys.exit(1)


def process_single_case(case_dir, field_name='meltHistory', time_value='0.00034',
                        output_file=None, export_vtk=False):
    """
    Process a single OpenFOAM case.

    Args:
        case_dir: Path to case directory (containing constant/, system/, time dirs)
        field_name: Field to visualize (default: meltHistory)
        time_value: Time step (default: 0.00034)
        output_file: Output image file path
        export_vtk: If True, also export VTK file
    """
    case_dir = Path(case_dir).resolve()

    # Create .foam file
    foam_file = case_dir / f"{case_dir.name}.foam"
    if not foam_file.exists():
        foam_file.touch()

    print(f"  Loading case: {case_dir.name}")

    # Read OpenFOAM case
    reader = OpenFOAMReader(FileName=str(foam_file))
    reader.MeshRegions = ['internalMesh']
    reader.CellArrays = [field_name, 'alpha.metal', 'T']

    # Update pipeline
    reader.UpdatePipeline()

    # Set time
    if reader.TimestepValues:
        target_time = float(time_value)
        closest_time = min(reader.TimestepValues, key=lambda x: abs(x - target_time))
        GetAnimationScene().AnimationTime = closest_time
        print(f"    Time: {closest_time}")

    # Apply threshold to show only metal region (alpha.metal > 0.5)
    threshold = Threshold(Input=reader)
    threshold.Scalars = ['CELLS', 'alpha.metal']
    # ParaView 5.10+ API
    threshold.LowerThreshold = 0.5
    threshold.UpperThreshold = 1.0
    threshold.ThresholdMethod = 'Between'
    threshold.UpdatePipeline()

    # Create render view
    renderView = CreateView('RenderView')
    renderView.ViewSize = [1920, 1080]
    renderView.Background = [1, 1, 1]

    # Show data
    display = Show(threshold, renderView)

    # Color by field
    ColorBy(display, ('CELLS', field_name))

    # Setup color map
    lut = GetColorTransferFunction(field_name)
    lut.ApplyPreset('Rainbow Desaturated', True)

    # Show color bar
    display.SetScalarBarVisibility(renderView, True)

    # Adjust camera
    renderView.ResetCamera()

    # Save screenshot
    if output_file:
        output_file = Path(output_file)
        output_file.parent.mkdir(parents=True, exist_ok=True)
        SaveScreenshot(str(output_file), renderView, ImageResolution=[1920, 1080])
        print(f"    ✓ Saved: {output_file}")

    # Export VTK if requested
    if export_vtk and output_file:
        vtk_file = output_file.with_suffix('.vtk')
        SaveData(str(vtk_file), threshold)
        print(f"    ✓ Exported VTK: {vtk_file}")

    # Cleanup
    Delete(display)
    Delete(threshold)
    Delete(reader)
    Delete(renderView)

    return True


def batch_process_runs(base_dir, field_name='meltHistory', time_value='0.00034',
                       output_dir='visualization_output', export_vtk=False):
    """
    Batch process all cases in runs directory.
    """
    base_dir = Path(base_dir)
    runs_dir = base_dir / 'runs'
    output_dir = base_dir / output_dir

    if not runs_dir.exists():
        print(f"ERROR: {runs_dir} not found")
        return

    print(f"\nSearching for cases in: {runs_dir}")

    # Find all cases
    cases = []
    for run_id_dir in sorted(runs_dir.iterdir()):
        if not run_id_dir.is_dir() or run_id_dir.name in ['plots', 'simulations', 'config.yaml']:
            continue

        for power_dir in sorted(run_id_dir.iterdir()):
            if not power_dir.is_dir():
                continue

            time_dir = power_dir / time_value
            if time_dir.exists() and (time_dir / field_name).exists():
                cases.append({
                    'path': power_dir,
                    'run_id': run_id_dir.name,
                    'power': power_dir.name
                })

    print(f"Found {len(cases)} cases\n")

    if not cases:
        print("No cases found!")
        return

    # Process each case
    success = 0
    for i, case_info in enumerate(cases, 1):
        print(f"[{i}/{len(cases)}] Run {case_info['run_id']}, Power {case_info['power']}")

        # Create output path
        output_file = output_dir / case_info['run_id'] / f"{case_info['power']}_{field_name}.png"

        try:
            process_single_case(
                case_info['path'],
                field_name=field_name,
                time_value=time_value,
                output_file=output_file,
                export_vtk=export_vtk
            )
            success += 1
        except Exception as e:
            print(f"    ✗ Error: {e}")

        print()

    print("=" * 80)
    print(f"Complete! Processed {success}/{len(cases)} cases")
    print(f"Output directory: {output_dir}")
    print("=" * 80)


def main():
    parser = argparse.ArgumentParser(description='Batch visualize OpenFOAM meltpool results')
    parser.add_argument('--time', default='0.00034', help='Time step to visualize')
    parser.add_argument('--field', default='meltHistory', help='Field to visualize')
    parser.add_argument('--output', default='visualization_output', help='Output directory')
    parser.add_argument('--vtk', action='store_true', help='Also export VTK files')
    parser.add_argument('--case', help='Process single case directory instead of batch')

    args = parser.parse_args()

    print("=" * 80)
    print("OpenFOAM Meltpool Batch Visualization")
    print("=" * 80)

    base_dir = Path(__file__).parent

    if args.case:
        # Process single case
        case_dir = Path(args.case)
        output_file = base_dir / args.output / f"{case_dir.name}_{args.field}.png"
        process_single_case(case_dir, args.field, args.time, output_file, args.vtk)
    else:
        # Batch process
        batch_process_runs(base_dir, args.field, args.time, args.output, args.vtk)


if __name__ == '__main__':
    main()
