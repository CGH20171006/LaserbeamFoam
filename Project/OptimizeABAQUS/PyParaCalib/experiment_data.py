from __future__ import annotations

from typing import Tuple

import numpy as np
import pandas as pd

from PyParaCalib.opt_config import BaseConfig


def load_experiment(cfg: BaseConfig) -> Tuple[np.ndarray, np.ndarray]:
    df = pd.read_csv(cfg.exp_csv, header=0)
    if df.shape[1] < 2:
        raise ValueError("data.csv must have >= 2 columns: time, stress")
    t_all = df.iloc[:, 0].to_numpy(float)
    s_all = df.iloc[:, 1].to_numpy(float)
    mask = (t_all >= cfg.t_min) & (t_all <= cfg.t_max)
    if mask.sum() == 0:
        raise ValueError("No points in fit window")
    return t_all[mask], s_all[mask]
