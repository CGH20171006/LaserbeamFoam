from __future__ import annotations

import argparse

from PyParaCalib.experiment_data import load_experiment
from PyParaCalib.opt_config import BayesConfig, GradientConfig, build_runs_root
from PyParaCalib.optimizer_bayes import run_bayesian_optimization
from PyParaCalib.optimizer_gradient import run_gradient_optimization


def main() -> None:
    parser = argparse.ArgumentParser(description="Abaqus+UMAT parameter optimization")
    parser.add_argument("--method", choices=["bayes", "gradient"], default="bayes")
    args = parser.parse_args()

    if args.method == "bayes":
        cfg = BayesConfig()
        exp_time, exp_stress = load_experiment(cfg)
        result = run_bayesian_optimization(cfg, exp_time, exp_stress)
    else:
        cfg = GradientConfig()
        cfg.runs_root = build_runs_root("gradient")
        exp_time, exp_stress = load_experiment(cfg)
        result = run_gradient_optimization(cfg, exp_time, exp_stress)

    if "cost" in result:
        print(f"\nBest SSE: {result['cost']:.4e}")


if __name__ == "__main__":
    main()
