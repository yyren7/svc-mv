#!/bin/bash
# Draw job files on ComfyUI and stop it afterwards, so it holds the GPU only while it draws.
#   nohup bash comfy_batch.sh <jobs.json>... > batch.log 2>&1 &
cd /root/autodl-tmp/ComfyUI || exit 1
nohup ./venv/bin/python main.py --listen 127.0.0.1 --port 8188 --disable-auto-launch > /root/autodl-tmp/comfy.log 2>&1 &
pid=$!
stop() {
    kill "$pid" 2>/dev/null
    wait "$pid" 2>/dev/null
    echo "comfyui stopped, gpu $(nvidia-smi --query-gpu=memory.used --format=csv,noheader)"
}
trap stop EXIT
trap 'exit 1' INT TERM HUP
for i in $(seq 1 120); do curl -s http://127.0.0.1:8188/system_stats > /dev/null && break; sleep 2; done
for f in "$@"; do
    echo "== $f $(date +%T)"
    /root/miniconda3/bin/python /root/autodl-tmp/comfy_gen.py "$f"
done
echo "== done $(date +%T)"
