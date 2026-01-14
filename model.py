# model.py
from pathlib import Path
from transformers import pipeline
import threading

_CKPT = Path("ckpts")   # 1. 原始字符串用正斜杠
_LOCK = threading.Lock()
_PIPELINE = None

def _load_model() -> pipeline:
    global _PIPELINE
    if _PIPELINE is None:
        with _LOCK:
            if _PIPELINE is None:
                _PIPELINE = pipeline(
                    "text-classification",
                    model=_CKPT.as_posix(),      # 2. 关键：转成正斜杠
                    tokenizer=_CKPT.as_posix(),
                    device=-1,
                    top_k=None
                )
    return _PIPELINE

def predict_sentiment(text: str) -> tuple[str, float]:
    pipe = _load_model()
    result = pipe(text[:512], top_k=None)[0]   # 一定 list
    # 统一取字段
    if isinstance(result, dict):
        label, score = result["label"], result["score"]
    else:                       # 旧版只给标签
        label, score = result, 1.0
    return str(label), float(score)
