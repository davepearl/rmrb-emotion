from transformers import pipeline
import threading

# 1. 从 HuggingFace Hub 加载（不再用本地文件夹）
_CKPT = "davepearl/tinybert-zh-sentiment"   # 你的 HF 仓库名

_LOCK = threading.Lock()
_PIPELINE = None

def _load_model() -> pipeline:
    global _PIPELINE
    if _PIPELINE is None:
        with _LOCK:
            if _PIPELINE is None:
                _PIPELINE = pipeline(
                    "text-classification",
                    model=_CKPT,          # Hub 仓库名
                    tokenizer=_CKPT,
                    device=-1,
                    top_k=None
                )
    return _PIPELINE

def predict_sentiment(text: str) -> tuple[str, float]:
    pipe = _load_model()
    result = pipe(text[:512], top_k=None)[0]   # 一定 list
    if isinstance(result, dict):
        return result["label"], float(result["score"])
    # 旧版只返回标签
    return str(result), 1.0
