#!/bin/bash
# 一图流 PV 在 AutoDL 上的环境：只在服务器上跑，本地 PC 不装任何东西。
#   bash onepic_setup.sh            # 装依赖、下模型，已存在的跳过
# 依赖装进单独的 $PV/pylib（--no-deps），借用 ComfyUI venv 里的 torch / transformers / spandrel / av，
# 不改 ComfyUI 自己的 venv。模型放 $PV/models。
set -uo pipefail
PV=${PV:-/root/autodl-tmp/pv}
PY=${PY:-/root/autodl-tmp/ComfyUI/venv/bin/python}
mkdir -p "$PV/pylib" "$PV/models"

# 依赖：Whisper（CTranslate2）、VAD 用的 onnxruntime、OpenCV；ComfyUI venv 里已有的不再装
"$PY" -m pip install -q --no-deps --timeout 60 -i "${PIP_INDEX:-https://mirrors.cloud.tencent.com/pypi/simple}" \
    --target "$PV/pylib" \
    faster-whisper ctranslate2 onnxruntime opencv-python-headless coloredlogs humanfriendly flatbuffers 2>&1 | tail -3

export HF_ENDPOINT=https://hf-mirror.com
get_hf() {  # repo file dest
    [ -s "$3" ] && return 0
    mkdir -p "$(dirname "$3")"
    curl -sL --retry 3 -o "$3.part" "$HF_ENDPOINT/$1/resolve/main/$2" && mv "$3.part" "$3"
}
# 抠人物：anime-segmentation (ISNet)
get_hf skytnt/anime-seg isnetis.onnx "$PV/models/anime-seg/isnetis.onnx"
# 深度：Depth Anything V2 Large（transformers 格式）
for f in config.json preprocessor_config.json model.safetensors; do
    get_hf depth-anything/Depth-Anything-V2-Large-hf $f "$PV/models/depth-anything-v2-large/$f"
done
# 歌词时间轴：faster-whisper large-v3
for f in config.json model.bin tokenizer.json vocabulary.json preprocessor_config.json; do
    get_hf Systran/faster-whisper-large-v3 $f "$PV/models/faster-whisper-large-v3/$f"
done
# 人物背后的补全：big-lama（TorchScript，IOPaint 用的那份），走 AutoDL 的学术加速下 GitHub
if [ ! -s "$PV/models/big-lama.pt" ]; then
    ( source /etc/network_turbo >/dev/null 2>&1
      curl -sL --retry 3 -o "$PV/models/big-lama.pt.part" \
          https://github.com/Sanster/models/releases/download/add_big_lama/big-lama.pt ) \
        && mv "$PV/models/big-lama.pt.part" "$PV/models/big-lama.pt"
fi
ls -la "$PV/models" "$PV/models"/*/
PYTHONPATH="$PV/pylib" "$PY" -c "import cv2, onnxruntime, ctranslate2, faster_whisper; print('ok', cv2.__version__, ctranslate2.__version__, ctranslate2.get_cuda_device_count())"
echo "== setup done"
