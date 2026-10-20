"""Speech / lyrics to text with timestamps (faster-whisper, CPU int8).

    .venv/Scripts/python scripts/transcribe.py audio.wav out.json [model] [language]

Models download from hf-mirror.com (huggingface.co is slow from here).
"""
import json
import os
import sys

os.environ.setdefault("HF_ENDPOINT", "https://hf-mirror.com")
from faster_whisper import WhisperModel  # noqa: E402

audio, out = sys.argv[1], sys.argv[2]
model = sys.argv[3] if len(sys.argv) > 3 else "medium"
lang = sys.argv[4] if len(sys.argv) > 4 else None
wm = WhisperModel(model, device="cpu", compute_type="int8")
segs, info = wm.transcribe(audio, language=lang, word_timestamps=True, vad_filter=True,
                           initial_prompt="以下是普通话的句子，使用简体中文。" if lang == "zh" else None)
rows = []
for s in segs:
    rows.append({"start": round(s.start, 2), "end": round(s.end, 2), "text": s.text.strip(),
                 "words": [{"start": round(w.start, 2), "end": round(w.end, 2), "word": w.word} for w in s.words or []]})
    print(f"[{s.start:6.1f}] {s.text.strip()}", flush=True)
json.dump({"language": info.language, "segments": rows}, open(out, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
