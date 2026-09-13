#!/usr/bin/env bash
# Run training jobs one after another on the VM (one GPU, one person at a time). Waits for any running
# turbine_tslm.training.train process first. Usage (on the VM, from the repo):
#   nohup scripts/vm_queue.sh configs/a.yaml "configs/b.yaml --predict-only" configs/c.yaml > outputs/queue.log 2>&1 &
# Each job's console log goes to outputs/<config-stem>[.predict].log; failures do not stop the queue.
set -u
export PATH="$HOME/.local/bin:$PATH" DATA_DIR="${DATA_DIR:-$HOME/data}" PYTHONUNBUFFERED=1 PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True
eval "$(grep "HF_TOKEN=" ~/.bashrc | head -1 | sed "s/^/export /; s/^export export/export/")"
cd "$(dirname "$0")/.."
mkdir -p outputs
while pgrep -f "[p]ython -m turbine_tslm.training.train" >/dev/null; do sleep 30; done
for job in "$@"; do
  cfg=${job%% *}
  extra=${job#"$cfg"}
  stem=$(basename "$cfg" .yaml)
  [[ "$extra" == *predict-only* ]] && stem="$stem.predict"
  echo "[queue] $(date +%T) start: $job" | tee -a outputs/queue.log
  flock /tmp/turbine_gpu.lock uv run python -m turbine_tslm.training.train $cfg $extra > "outputs/$stem.log" 2>&1
  echo "[queue] $(date +%T) done (exit $?): $job" | tee -a outputs/queue.log
done
echo "[queue] $(date +%T) queue finished" | tee -a outputs/queue.log
