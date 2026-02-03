#!/bin/bash -l
#SBATCH -A p200943
#SBATCH -p cpu
#SBATCH -q long
#SBATCH -N 1
#SBATCH -n 256
#SBATCH -t 144:00:00
#SBATCH --job-name=bayes
#SBATCH --output=bayes_%j.out
#SBATCH --error=bayes_%j.err

set -euo pipefail
cd "$SLURM_SUBMIT_DIR"

module load Apptainer
# If conda is not available in non-interactive shells, uncomment and adjust:
# source ~/miniconda3/etc/profile.d/conda.sh
conda activate meltpool-postproc

python bayes_opt_HPC.py
