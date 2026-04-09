#!/usr/bin/env pvpython
"""
Test script to verify ParaView Python API is working and test on a single case.
"""

import sys
from pathlib import Path

try:
    from paraview.simple import *
    print("✓ ParaView Python API imported successfully")
except ImportError as e:
    print(f"✗ Failed to import ParaView: {e}")
    sys.exit(1)

# Test on a single case
base_dir = Path(__file__).parent
test_case = base_dir / "runs" / "27" / "260W"

if not test_case.exists():
    print(f"✗ Test case not found: {test_case}")
    # Find any available case
    runs_dir = base_dir / "runs"
    for run_dir in sorted(runs_dir.iterdir()):
        if run_dir.is_dir() and run_dir.name.isdigit():
            for power_dir in run_dir.iterdir():
                if power_dir.is_dir() and (power_dir / "0.00034").exists():
                    test_case = power_dir
                    print(f"  Using alternative test case: {test_case}")
                    break
            if test_case.exists():
                break

if not test_case.exists():
    print("✗ No valid test cases found")
    sys.exit(1)

print(f"\nTesting with case: {test_case}")
print(f"  Run ID: {test_case.parent.name}")
print(f"  Power: {test_case.name}")

# Create .foam file
foam_file = test_case / f"{test_case.name}.foam"
if not foam_file.exists():
    foam_file.touch()
    print(f"  Created: {foam_file.name}")

try:
    # Load OpenFOAM case
    print("\n1. Loading OpenFOAM case...")
    reader = OpenFOAMReader(FileName=str(foam_file))
    reader.MeshRegions = ['internalMesh']

    # Check available arrays
    print("   Updating pipeline...")
    reader.UpdatePipeline()

    print(f"   ✓ Case loaded successfully")

    # Print available time steps
    if reader.TimestepValues:
        print(f"\n2. Available time steps: {len(reader.TimestepValues)}")
        print(f"   First: {reader.TimestepValues[0]}")
        print(f"   Last: {reader.TimestepValues[-1]}")

        # Check if 0.00034 exists
        target_time = 0.00034
        closest = min(reader.TimestepValues, key=lambda x: abs(x - target_time))
        print(f"   Closest to 0.00034: {closest}")

    # Print available cell arrays
    print(f"\n3. Available cell arrays:")
    available_arrays = reader.CellData.keys()
    for arr in available_arrays:
        print(f"   - {arr}")

    # Check for required fields
    required_fields = ['meltHistory', 'alpha.metal', 'T']
    print(f"\n4. Checking required fields:")
    for field in required_fields:
        if field in available_arrays:
            print(f"   ✓ {field}")
        else:
            print(f"   ✗ {field} (missing)")

    # Test threshold filter
    print(f"\n5. Testing threshold filter...")
    if 'alpha.metal' in available_arrays:
        threshold = Threshold(Input=reader)
        threshold.Scalars = ['CELLS', 'alpha.metal']
        threshold.ThresholdRange = [0.5, 1.0]
        threshold.UpdatePipeline()
        print(f"   ✓ Threshold filter applied successfully")
        Delete(threshold)
    else:
        print(f"   ⚠ Skipping (alpha.metal not available)")

    # Test render view
    print(f"\n6. Testing render view...")
    renderView = CreateView('RenderView')
    renderView.ViewSize = [800, 600]
    print(f"   ✓ Render view created")
    Delete(renderView)

    # Cleanup
    Delete(reader)

    print("\n" + "="*60)
    print("✓ All tests passed!")
    print("="*60)
    print("\nYou can now run the batch visualization script:")
    print(f"  pvpython batch_visualize_simple.py")

except Exception as e:
    print(f"\n✗ Error during testing: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)
