"""Re-embed existing segment transcripts to a NEW versioned index; never overwrite legacy vectors.
Run from repository root: python scripts/reindex-remote.py --source data/index --output data/indexes/MODEL-VERSION
Set VRAG_INDEX_DIR to that output before restarting the API. No camera uploads or local inference.
"""
import argparse
import asyncio
import json
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import numpy as np
from vrag.settings import store
from vrag.remote import space_id
from vrag.routing import route

async def build(source, output):
    if output.exists():
        raise ValueError('output must be a new versioned directory')
    _, cfg = store.snapshot()
    rule = cfg.features.get('rag.text_embeddings')
    if not rule or rule.strategy != 'single':
        raise ValueError('configure one remote text embedding provider first')
    p = cfg.providers[rule.providers[0]]
    segments = json.loads((source / 'segments.json').read_text())
    if not segments:
        raise ValueError('source has no segments')
    vectors = []
    for s in segments:
        out, status = await route(cfg, 'rag.text_embeddings', {'text':f'title: {s["title"]} | text: {s["text"]}'})
        if not out.embedding:
            raise ValueError('remote embedding failed: '+str(status))
        vectors.append(out.embedding)
    matrix = np.asarray(vectors, dtype=np.float32)
    if matrix.ndim != 2 or not np.isfinite(matrix).all():
        raise ValueError('invalid embedding matrix')
    matrix /= np.linalg.norm(matrix, axis=1, keepdims=True)
    output.mkdir(parents=True)
    np.save(output / 'text.npy', matrix)
    (output / 'segments.json').write_text(json.dumps(segments))
    (output / 'manifest.json').write_text(json.dumps({'model':p.model, 'embedding_space':space_id(p), 'dimension':matrix.shape[1], 'mrl_dims':[matrix.shape[1]], 'views':{'text':{'count':len(segments)}}, 'segments':len(segments)}))
    print(f'Created {output}: {len(segments)} segments, {matrix.shape[1]} dimensions. Set VRAG_INDEX_DIR and restart; legacy index unchanged.')

if __name__ == '__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--source',type=Path,required=True);parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args();asyncio.run(build(args.source,args.output))
