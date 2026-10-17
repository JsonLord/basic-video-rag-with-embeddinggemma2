"""Brute-force cosine search over the per-view matrices, with Matryoshka truncation at query time.

Only ~500 segments, so a numpy matmul beats any ANN index here and keeps the MRL comparison exact:
every dim is searched against the same stored 768d vectors, truncated then re-normalised.
"""

import json
from functools import lru_cache

import numpy as np

from .config import DIMS, INDEX_DIR, VIEWS

HYBRID_VIEWS = ["text", "video", "audio"]
RRF_K = 60


def truncate(x: np.ndarray, dim: int) -> np.ndarray:
    """MRL truncation. Re-normalising is required: a sliced unit vector is no longer unit length."""
    x = x[..., :dim]
    return x / np.maximum(np.linalg.norm(x, axis=-1, keepdims=True), 1e-12)


class Index:
    def __init__(self):
        base = INDEX_DIR
        pointer = base / 'CURRENT'
        if pointer.exists():
            revision = pointer.read_text().strip()
            if len(revision)!=32 or not all(c in '0123456789abcdef' for c in revision):raise ValueError('invalid index revision')
            base = base / 'revisions' / revision
        self.path = base
        self.segments: list[dict] = json.loads((base / "segments.json").read_text()) if (base / "segments.json").exists() else []
        manifest_path = base / 'manifest.json'
        manifest = json.loads(manifest_path.read_text()) if manifest_path.exists() else {}
        self.dims = manifest.get('mrl_dims', [manifest['dimension']]) if 'dimension' in manifest else DIMS
        self.by_id = {s["id"]: i for i, s in enumerate(self.segments)}
        self.views = {v: np.load(base / f"{v}.npy", mmap_mode="r", allow_pickle=False) for v in VIEWS if (base / f"{v}.npy").exists()}
        for matrix in self.views.values():
            if (matrix.ndim != 2 or matrix.shape[0] != len(self.segments)
                or matrix.dtype.kind != 'f' or matrix.nbytes > 512 * 1024 * 1024
                or not 1 <= matrix.shape[1] <= 16384
                or ('dimension' in manifest and matrix.shape[1] != manifest['dimension'])
                or any(d < 1 or d > matrix.shape[1] for d in self.dims)):
                raise ValueError('invalid_index_shape_or_dimensions')
            for offset in range(0, len(matrix), 1024):
                block=matrix[offset:offset+1024]
                if not np.isfinite(block).all() or (np.linalg.norm(block,axis=1)==0).any():
                    raise ValueError('invalid_index_vectors')
        self._trunc = {}

    @property
    def available_views(self) -> list[str]:
        vs = list(self.views)
        if all(v in self.views for v in HYBRID_VIEWS):
            vs.append("hybrid")
        return vs

    def matrix(self, view: str, dim: int) -> np.ndarray:
        key = (view, dim)
        if key not in self._trunc:
            self._trunc[key] = truncate(self.views[view], dim)
        return self._trunc[key]

    def scores(self, q: np.ndarray, view: str, dim: int) -> np.ndarray:
        return self.matrix(view, dim) @ truncate(q, dim)

    def rank(self, q: np.ndarray, view: str, dim: int, mask: np.ndarray | None = None) -> tuple[np.ndarray, np.ndarray]:
        """Full ranking (indices, scores). 'hybrid' fuses text/video/audio rankings with reciprocal rank fusion."""
        if view == "hybrid":
            fused = np.zeros(len(self.segments))
            for v in HYBRID_VIEWS:
                order = np.argsort(-self.scores(q, v, dim))
                fused[order] += 1.0 / (RRF_K + np.arange(1, len(order) + 1))
            s = fused
        else:
            s = self.scores(q, view, dim)
        if mask is not None:
            s = np.where(mask, s, -np.inf)
        order = np.argsort(-s)
        return order, s[order]

    def search(self, q: np.ndarray, view: str = "fused", dim: int = 768, k: int = 10,
               video_id: str | None = None) -> list[dict]:
        mask = None
        if video_id:
            mask = np.array([s["video_id"] == video_id for s in self.segments])
        order, scores = self.rank(q, view, dim, mask)
        return [{**self.segments[i], "score": float(sc), "rank": r + 1}
                for r, (i, sc) in enumerate(zip(order[:k], scores[:k])) if np.isfinite(sc)]

    def storage_bytes(self, dim: int, dtype_bytes: int = 4) -> int:
        return len(self.segments) * dim * dtype_bytes


@lru_cache(maxsize=1)
def get_index() -> Index:
    try:
        return Index()
    except (ValueError, OSError, KeyError, TypeError):
        from .providers import ProviderFailure
        raise ProviderFailure('index_invalid_or_incompatible') from None


__all__ = ["Index", "get_index", "truncate", "DIMS"]
