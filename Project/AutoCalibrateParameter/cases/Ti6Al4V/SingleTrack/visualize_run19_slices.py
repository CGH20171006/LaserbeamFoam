#!/usr/bin/env pvpython
"""
Multi-slice visualization for Ti6Al4V run 19.
Slices along Y axis from 0 to 800um, every 40um.

Usage:
    pvpython visualize_run19_slices.py
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


def process_case_multi_slice(case_dir, output_dir, y_positions,
                             field='meltHistory', time_val=TIME_VALUE):
    case_dir = Path(case_dir)
    output_dir = Path(output_dir)

    foam_file = case_dir / f"{case_dir.name}.foam"
    foam_file.touch(exist_ok=True)

    print(f"  Loading: {case_dir.name}")

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
    slice_filter.SliceType.Normal = [0.0, 1.0, 0.0]

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

    view.CameraViewUp = [0.0, 0.0, 1.0]

    output_dir.mkdir(parents=True, exist_ok=True)
    count = 0

    for y in y_positions:
        y_um = int(round(y * 1e6))

        slice_filter.SliceType.Origin = [0.0, y, 0.0]
        slice_filter.UpdatePipeline()

        view.CameraPosition = [0.0, y + 0.01, 0.0]
        view.CameraFocalPoint = [0.0, y, 0.0]
        view.ResetCamera()

        out_file = output_dir / f"{case_dir.name}_Y{y_um:04d}um_{field}.png"
        SaveScreenshot(str(out_file), view, ImageResolution=[1920, 1080])
        print(f"    Y={y_um:4d}um  ✓")
        count += 1

    Delete(display)
    Delete(slice_filter)
    Delete(threshold)
    Delete(reader)
    Delete(view)

    return count


def main():
    base_dir = Path(__file__).parent
    run_dir = base_dir / "runs" / "19"
    output_dir = base_dir / "visualization_output" / "19_slices"

    # Y: 0 to 800um, every 40um
    y_positions = [i * 0.00004 for i in range(21)]

    print("=" * 80)
    print("Ti6Al4V Run 19 - Multi-Slice Visualization")
    print("=" * 80)
    print(f"Time step: {TIME_DIR}")
    print(f"Y range: 0 ~ 800 um, step 40 um ({len(y_positions)} slices)")
    print(f"Output: {output_dir}")
    print()

    powers = sorted([d for d in run_dir.iterdir() if d.is_dir()])
    total = len(powers) * len(y_positions)
    done = 0

    for power_dir in powers:
        print(f"[{power_dir.name}] ({len(y_positions)} slices)")
        setup_case_links(power_dir, base_dir)
        case_output = output_dir / power_dir.name
        n = process_case_multi_slice(power_dir, case_output, y_positions)
        done += n
        print()

    print("=" * 80)
    print(f"Complete! Generated {done}/{total} images")
    print(f"Output: {output_dir}")
    print("=" * 80)


if __name__ == '__main__':
    main()
