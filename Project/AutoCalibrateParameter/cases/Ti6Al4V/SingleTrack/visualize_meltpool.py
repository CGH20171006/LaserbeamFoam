#!/usr/bin/env pvpython
"""
Batch visualization for Ti6Al4V SingleTrack results.
Slice at Y=0.0004, XZ plane view, meltHistory 0-1, white background.

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

TIME_VALUE = 0.0003
TIME_DIR = "0.0003"


def setup_case_links(run_dir, base_dir):
    run_dir = Path(run_dir)
    base_dir = Path(base_dir)
    for name in ['constant', 'system']:
        link = run_dir / name
        if not link.exists():
            os.symlink(base_dir / name, link, target_is_directory=True)


def visualize_case(case_dir, output_file, field='meltHistory', time_val=TIME_VALUE):
    case_dir = Path(case_dir)

    foam_file = case_dir / f"{case_dir.name}.foam"
    foam_file.touch(exist_ok=True)

    print(f"  Processing: {case_dir.name}")

    try:
        reader = OpenFOAMReader(FileName=str(foam_file))
        reader.MeshRegions = ['internalMesh']
        reader.CellArrays = [field, 'alpha.metal', 'T']
        reader.UpdatePipeline()

        if reader.TimestepValues:
            closest_time = min(reader.TimestepValues, key=lambda x: abs(x - time_val))
            GetAnimationScene().AnimationTime = closest_time

        threshold = Threshold(Input=reader)
        threshold.Scalars = ['CELLS', 'alpha.metal']
        threshold.LowerThreshold = 0.5
        threshold.UpperThreshold = 1.0
        threshold.ThresholdMethod = 'Between'
        threshold.UpdatePipeline()

        slice_filter = Slice(Input=threshold)
        slice_filter.SliceType = 'Plane'
        slice_filter.SliceType.Origin = [0.0, 0.0004, 0.0]
        slice_filter.SliceType.Normal = [0.0, 1.0, 0.0]
        slice_filter.UpdatePipeline()

        view = CreateView('RenderView')
        view.ViewSize = [1920, 1080]
        view.UseColorPaletteForBackground = 0
        view.Background = [1, 1, 1]

        display = Show(slice_filter, view)
        ColorBy(display, ('CELLS', field))

        lut = GetColorTransferFunction(field)
        lut.ApplyPreset('Rainbow Desaturated', True)
        lut.RescaleTransferFunction(0.0, 1.0)
        display.SetScalarBarVisibility(view, True)

        view.CameraPosition = [0.0, 0.01, 0.0]
        view.CameraFocalPoint = [0.0, 0.0004, 0.0]
        view.CameraViewUp = [0.0, 0.0, 1.0]
        view.ResetCamera()

        output_file = Path(output_file)
        output_file.parent.mkdir(parents=True, exist_ok=True)
        SaveScreenshot(str(output_file), view, ImageResolution=[1920, 1080])
        print(f"    ✓ Saved: {output_file.name}")

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

    print("=" * 80)
    print("Ti6Al4V - Meltpool Batch Visualization")
    print("=" * 80)
    print(f"Base directory: {base_dir}")
    print(f"Time step: {TIME_DIR}")
    print(f"Output: {output_dir}")
    print()

    cases = []
    for run_id_dir in sorted(runs_dir.iterdir()):
        if not run_id_dir.is_dir() or not run_id_dir.name.isdigit():
            continue
        for power_dir in sorted(run_id_dir.iterdir()):
            if not power_dir.is_dir():
                continue
            time_dir = power_dir / TIME_DIR
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

    success = 0
    for i, case in enumerate(cases, 1):
        print(f"[{i}/{len(cases)}] Run {case['run_id']}, Power {case['power']}")
        setup_case_links(case['path'], base_dir)
        output_file = output_dir / case['run_id'] / f"{case['power']}_meltHistory.png"
        if visualize_case(case['path'], output_file):
            success += 1
        print()

    print("=" * 80)
    print(f"Complete! Successfully processed {success}/{len(cases)} cases")
    print(f"Output saved to: {output_dir}")
    print("=" * 80)


if __name__ == '__main__':
    main()
