"""EmbeddingGemma 2 wrapper: one model instance, prompt conventions, and the per-view corpus inputs."""

import numpy as np
import torch

from .config import EMBED_MODEL
from .segment import media_paths

_model = None


def get_model():
    global _model
    if _model is None:
        from sentence_transformers import SentenceTransformer

        # bf16, never fp16: the model card warns fp16 silently produces NaN / degraded embeddings.
        dtype = torch.bfloat16 if torch.cuda.is_bf16_supported() else torch.float32
        _model = SentenceTransformer(EMBED_MODEL, device="cuda", model_kwargs={"torch_dtype": dtype})
    return _model


def doc_text(seg: dict) -> str:
    return f"title: {seg['title']} | text: {seg['text']}"


def view_input(view: str, seg: dict):
    """The model input for one segment under one view. Media inputs take no task prefix."""
    m = media_paths(seg)
    if view == "text":
        return doc_text(seg)
    if view == "frame":
        return {"image": str(m["frame"])}
    if view == "video":
        return {"video": str(m["clip"])}
    if view == "audio":
        return {"audio": str(m["audio"])}
    if view == "fused":
        return {"text": f"{doc_text(seg)} <|video|> <|audio|>", "video": str(m["clip"]), "audio": str(m["audio"])}
    raise ValueError(f"unknown view {view!r}")


def encode_query(query: str) -> np.ndarray:
    """Full 768d, unit-norm. Truncation to smaller MRL dims happens at search time."""
    return get_model().encode(query, prompt_name="SearchQuery", convert_to_numpy=True).astype(np.float32)


def encode_image_query(path: str) -> np.ndarray:
    return get_model().encode({"image": path}, convert_to_numpy=True).astype(np.float32)


def encode_view(view: str, segs: list[dict], batch_size: int) -> np.ndarray:
    inputs = [view_input(view, s) for s in segs]
    embs = get_model().encode(inputs, batch_size=batch_size, convert_to_numpy=True, show_progress_bar=True)
    return embs.astype(np.float32)
