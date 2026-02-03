from __future__ import annotations

from pathlib import Path
from typing import List

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

import numpy as np


def save_comparison_plot(
    work_dir: Path,
    job_name: str,
    exp_time: np.ndarray,
    exp_stress: np.ndarray,
    sim_time: np.ndarray,
    sim_stress: np.ndarray,
    sse: float,
) -> None:
    try:
        plt.figure(figsize=(10, 6))
        plt.plot(exp_time, exp_stress, "ko", label="Experiment", markersize=4, fillstyle="none")
        plt.plot(sim_time, sim_stress, "r-", label=f"Sim (SSE: {sse:.2e})", linewidth=2)
        plt.title(f"Result: {job_name}\nSSE: {sse:.2e}")
        plt.xlabel("Time (s)")
        plt.ylabel("Stress (MPa)")
        plt.legend()
        plt.grid(True, alpha=0.3)

        png_path = Path(work_dir) / f"{job_name}_result.png"
        plt.savefig(png_path, dpi=150)
        plt.close()
        print(f"   [PLOT] Saved: {png_path}")
    except Exception as exc:
        print(f"   [PLOT ERROR] {exc}")


def save_convergence_plot(runs_root: Path, all_y: List[float], n_initial: int) -> None:
    try:
        _, ax = plt.subplots(figsize=(10, 6))

        n_evals = len(all_y)
        x = np.arange(1, n_evals + 1)
        best_so_far = np.minimum.accumulate(all_y)

        ax.scatter(x, all_y, c="blue", alpha=0.5, s=20, label="SSE per evaluation")
        ax.plot(x, best_so_far, "r-", linewidth=2, label="Best SSE so far")

        if 0 < n_initial < n_evals:
            ax.axvline(
                x=n_initial,
                color="green",
                linestyle="--",
                linewidth=1.5,
                label=f"Initial sampling end (n={n_initial})",
            )

        min_idx = int(np.argmin(all_y))
        min_val = all_y[min_idx]
        ax.scatter(
            [min_idx + 1],
            [min_val],
            c="red",
            s=150,
            marker="*",
            zorder=5,
            edgecolors="black",
            linewidths=1,
            label=f"Minimum: {min_val:.4e} (eval #{min_idx + 1})",
        )

        ax.annotate(
            f"Min: {min_val:.4e}\n(#{min_idx + 1})",
            xy=(min_idx + 1, min_val),
            xytext=(min_idx + 1 + n_evals * 0.1, min_val * 2),
            arrowprops=dict(arrowstyle="->", color="darkred", lw=1.5),
            fontsize=10,
            color="darkred",
            fontweight="bold",
        )

        ax.set_xlabel("Evaluation Number", fontsize=12)
        ax.set_ylabel("SSE", fontsize=12)
        ax.set_title("SSE Convergence Plot", fontsize=14)
        ax.legend(loc="upper right")
        ax.grid(True, alpha=0.3)
        ax.set_yscale("log")

        plt.tight_layout()

        png_path = runs_root / "convergence_plot.png"
        plt.savefig(png_path, dpi=150)
        plt.close()
        print(f"   [PLOT] Convergence plot saved: {png_path}")
    except Exception as exc:
        print(f"   [PLOT ERROR] Failed to create convergence plot: {exc}")


def save_iteration_plot(work_dir: Path, job_name: str, sse_history: List[float]) -> None:
    if not sse_history:
        return
    try:
        _, ax = plt.subplots(figsize=(10, 6))

        x = np.arange(1, len(sse_history) + 1)
        best_so_far = np.minimum.accumulate(sse_history)

        ax.scatter(x, sse_history, c="blue", alpha=0.5, s=20, label="SSE per evaluation")
        ax.plot(x, best_so_far, "r-", linewidth=2, label="Best SSE so far")

        ax.set_xlabel("Evaluation Number", fontsize=12)
        ax.set_ylabel("SSE", fontsize=12)
        ax.set_title(f"Iteration Plot: {job_name}", fontsize=14)
        ax.legend(loc="upper right")
        ax.grid(True, alpha=0.3)
        ax.set_yscale("log")

        plt.tight_layout()

        png_path = Path(work_dir) / f"{job_name}_iteration.png"
        plt.savefig(png_path, dpi=150)
        plt.close()
        print(f"   [PLOT] Iteration plot saved: {png_path}")
    except Exception as exc:
        print(f"   [PLOT ERROR] Failed to create iteration plot: {exc}")
