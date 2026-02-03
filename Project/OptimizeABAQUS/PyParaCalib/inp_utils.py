"""Rewrite Abaqus .inp by replacing *User Material constants with 18 parameters.

Matches MATLAB update_inp_18_params():
- Find the line containing '*User Material'
- Write it as-is
- Skip the next 3 lines in the template
- Write 18 parameters formatted with 10 significant digits, split into:
    8 + 8 + 2 values over 3 lines

If your template has a different number of constant lines, change SKIP_LINES.
"""

from __future__ import annotations

from pathlib import Path
from typing import Sequence

import numpy as np

SKIP_LINES = 3


def update_inp_18_params(template_file: Path | str, new_file: Path | str, p: Sequence[float]) -> None:
    template_file = Path(template_file)
    new_file = Path(new_file)

    p = np.asarray(p, dtype=float).reshape(-1)
    if p.size != 18:
        raise ValueError("Expected exactly 18 parameters")

    def fmt(vals):
        return ", ".join(f"{v:.10g}" for v in vals)

    with template_file.open("r", errors="ignore") as fin, new_file.open("w", newline="\n") as fout:
        it = iter(fin)
        for line in it:
            if "*User Material" in line:
                fout.write(line.rstrip("\n") + "\n")

                # Skip template constant lines
                for _ in range(SKIP_LINES):
                    try:
                        next(it)
                    except StopIteration:
                        break

                fout.write(fmt(p[0:8]) + "\n")
                fout.write(fmt(p[8:16]) + "\n")
                fout.write(fmt(p[16:18]) + "\n")
            else:
                fout.write(line.rstrip("\n") + "\n")
