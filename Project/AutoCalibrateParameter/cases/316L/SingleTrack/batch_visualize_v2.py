#!/usr/bin/env pvpython
"""
Batch visualization script for OpenFOAM meltpool results.
Handles cases where runs/ contains only time directories without constant/system.

Usage:
    pvpython batch_visualize_v2.py [options]

Options:
    --time VALUE      Time step to visualize (default: 0.00034)
    --field FIELD     Field to visualize (default: meltHistory)
    --output DIR      Output directory (default: ./visualization_output)
    --vtk             Also export VTK files
    --symlink         Create symlinks for constant/system in each run
"""

import os
import sys
import argparse
import shutil
from pathlib import Path

try:
    from paraview.simple import *
except ImportError:
    print("ERROR: This script must be run with pvpython")
    print("Try: pvpython batch_visualize_v2.py")
    sys.exit(1)


def create_case_structure(run_dir, base_constant, base_system):
    """
    Create symlinks to constant/ and system/ directories if they don't exist.

    Args:
        run_dir: Run directory (e.g., runs/27/260W/)
        base_constant: Path to base constant/ directory
        base_system: Path to base system/ directory
    """
    run_dir = Path(run_dir)

    # Create symlinks
    constant_link = run_dir / "constant"
    system_link = run_dir / "system"

    if not constant_link.exists():
        constant_link.symlink_to(base_constant, target_is_directory=True)
        print(f"    Created symlink: constant -> {base_constant}")

    if not system_link.exists():
        system_link.symlink_to(base_system, target_is_directory=True)
        print(f"    Created symlink: system -> {base_system}")


def process_single_case(case_dir, field_name='meltHistory', time_value='0.00034',
                        output_file=None, export_vtk=False,
                        base_constant=None, base_system=None):
    """
    Process a single OpenFOAM case.

    Args:
        case_dir: Path to case directory
        field_name: Field to visualize
        time_value: Time step
        output_file: Output image file path
        export_vtk: If True, also export VTK file
        base_constant: Path to base constant/ directory
        base_system: Path to base system/ directory
    """
    case_dir = Path(case_dir).resolve()

    # Ensure constant/ and system/ exist (via symlinks if needed)
    if base_constant and base_system:
        create_case_structure(case_dir, base_constant, base_system)

    # Create .foam file
    foam_file = case_dir / f"{case_dir.name}.foam"
    if not foam_file.exists():
        foam_file.touch()

    print(f"  Loading case: {case_dir.name}")

    try:
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
        else:
            print(f"    Warning: No time steps found")
            return False

        # Check if field exists
        available_fields = [arr for arr in reader.CellData.keys()]
        if field_name not in available_fields:
            print(f"    Warning: Field '{field_name}' not found. Available: {available_fields}")
            return False

        # Apply threshold to show only metal region (alpha.metal > 0.5)
        if 'alpha.metal' in available_fields:
            threshold = Threshold(Input=reader)
            threshold.Scalars = ['CELLS', 'alpha.metal']
            # ParaView 5.10+ API
            threshold.LowerThreshold = 0.5
            threshold.UpperThreshold = 1.0
            threshold.ThresholdMethod = 'Between'
            threshold.UpdatePipeline()
            data_source = threshold
        else:
            print(f"    Warning: alpha.metal not found, showing full domain")
            data_source = reader

        # Create render view
        renderView = CreateView('RenderView')
        renderView.ViewSize = [1920, 1080]
        renderView.Background = [1, 1, 1]

        # Show data
        display = Show(data_source, renderView)

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
            SaveData(str(vtk_file), data_source)
            print(f"    ✓ Exported VTK: {vtk_file}")

        # Cleanup
        Delete(display)
        if 'alpha.metal' in available_fields:
            Delete(threshold)
        Delete(reader)
        Delete(renderView)

        return True

    except Exception as e:
        print(f"    ✗ Error: {e}")
        import traceback
        traceback.print_exc()
        return False


def batch_process_runs(base_dir, field_name='meltHistory', time_value='0.00034',
                       output_dir='visualization_output', export_vtk=False,
                       use_symlinks=True):
    """
    Batch process all cases in runs directory.
    """
    base_dir = Path(base_dir)
    runs_dir = base_dir / 'runs'
    output_dir = base_dir / output_dir

    # Base case structure
    base_constant = base_dir / 'constant'
    base_system = base_dir / 'system'

    if not base_constant.exists() or not base_system.exists():
        print(f"ERROR: Base case structure not found")
        print(f"  constant/: {base_constant.exists()}")
        print(f"  system/: {base_system.exists()}")
        return

    if not runs_dir.exists():
        print(f"ERROR: {runs_dir} not found")
        return

    print(f"\nSearching for cases in: {runs_dir}")
    print(f"Base constant: {base_constant}")
    print(f"Base system: {base_system}")

    # Find all cases
    cases = []
    for run_id_dir in sorted(runs_dir.iterdir()):
        if not run_id_dir.is_dir() or run_id_dir.name in ['plots', 'simulations']:
            continue

        # Skip non-numeric directories
        if not run_id_dir.name.isdigit():
            continue

        for power_dir in sorted(run_id_dir.iterdir()):
            if not power_dir.is_dir():
                continue

            time_dir = power_dir / time_value
            if time_dir.exists():
                # Check if field file exists
                field_file = time_dir / field_name
                if field_file.exists():
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

        if process_single_case(
            case_info['path'],
            field_name=field_name,
            time_value=time_value,
            output_file=output_file,
            export_vtk=export_vtk,
            base_constant=base_constant if use_symlinks else None,
            base_system=base_system if use_symlinks else None
        ):
            success += 1

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
    parser.add_argument('--no-symlink', action='store_true', help='Do not create symlinks')
    parser.add_argument('--case', help='Process single case directory instead of batch')

    args = parser.parse_args()

    print("=" * 80)
    print("OpenFOAM Meltpool Batch Visualization v2")
    print("=" * 80)

    base_dir = Path(__file__).parent

    if args.case:
        # Process single case
        case_dir = Path(args.case)
        output_file = base_dir / args.output / f"{case_dir.name}_{args.field}.png"

        base_constant = base_dir / 'constant'
        base_system = base_dir / 'system'

        process_single_case(
            case_dir,
            args.field,
            args.time,
            output_file,
            args.vtk,
            base_constant if not args.no_symlink else None,
            base_system if not args.no_symlink else None
        )
    else:
        # Batch process
        batch_process_runs(
            base_dir,
            args.field,
            args.time,
            args.output,
            args.vtk,
            not args.no_symlink
        )


if __name__ == '__main__':
    main()
