"""CPU RAG facade: fail explicitly on incompatible index/provider combinations."""
import asyncio
import base64
import hashlib
import json
import os
import time
from datetime import datetime, timezone
import numpy as np
from .config import DATA, INDEX_DIR, VIDEOS_DIR
from .index import get_index
from .providers import ProviderFailure
from .routing import route
from .settings import store

def space_id(provider):
    # Endpoint reference plus model and dimension identify a distinct embedding space.
    return hashlib.sha256(f'{os.environ.get(provider.base_url_env, "")}:{provider.model}'.encode()).hexdigest()[:16]

async def query(text, config=None):
    if config is None:
        _, config = store.snapshot()
    rule = config.features.get('rag.text_embeddings')
    if not rule or not rule.enabled or rule.strategy != 'single':
        raise ProviderFailure('embedding_provider_unavailable')
    p = config.providers[rule.providers[0]]
    manifest_path = get_index().path / 'manifest.json'
    manifest = json.loads(manifest_path.read_text()) if manifest_path.exists() else {}
    if manifest.get('embedding_space') != space_id(p):
        raise ProviderFailure('index_incompatible_reembed_required')
    out, statuses = await route(config, 'rag.text_embeddings', {'text': text})
    if out.embedding is None:
        raise ProviderFailure(statuses[-1]['status'] if statuses else 'embedding_provider_unavailable')
    if len(out.embedding) != manifest.get('dimension'):
        raise ProviderFailure('index_dimension_mismatch')
    q = np.asarray(out.embedding, dtype=np.float32)
    return q / np.linalg.norm(q)

def encode_query(text):
    return asyncio.run(query(text))

def encode_image_query(path):
    raise ProviderFailure('image_embeddings_unsupported')

def build_messages(question, hits, use_video, use_audio):
    if use_audio:
        raise ProviderFailure('rag_audio_unsupported_use_remote_transcription')
    text = 'Answer only from these clips and cite [n]. Say when evidence is insufficient.\nQuestion: ' + question
    images = []
    for n, h in enumerate(hits, 1):
        text += f'\n[{n}] {h["title"]} {h["start"]}-{h["end"]} seconds: {h["text"]}'
        if use_video:
            # Existing ingestion produces a bounded midpoint frame per segment. Remote models receive bytes, never file://.
            frame = VIDEOS_DIR / h['video_id'] / 'segments' / f'{h["idx"]:03d}.jpg'
            if frame.exists() and frame.stat().st_size <= 1024 * 1024:
                images.append('data:image/jpeg;base64,' + base64.b64encode(frame.read_bytes()).decode())
    return {'text': text[:64000], 'images': images[:8]}

async def _answer(question, view, dim, k, use_video, use_audio):
    start = time.monotonic()
    _, config = store.snapshot()
    hits = get_index().search(await query(question, config), view=view, dim=dim, k=min(k, 8))
    retrieve = time.monotonic() - start
    out, statuses = await route(config, 'rag.reasoning', build_messages(question, hits, use_video, use_audio))
    if not out.text:
        raise ProviderFailure('reasoning_provider_unavailable')
    result = {'question': question, 'answer': out.text, 'clips': hits,
            'settings': {'view': view, 'dim': dim, 'k': k, 'use_video': use_video, 'use_audio': use_audio},
            'usage': {'prompt_tokens': 0, 'completion_tokens': 0}, 'usage_available': False,
            'provider_results': statuses, 'timing': {'retrieve_s': retrieve, 'generate_s': time.monotonic()-start-retrieve},
            'created_at': datetime.now(timezone.utc).isoformat()}
    if os.environ.get('VRAG_SAVE_ANSWERS', 'true').lower() == 'true':
        history = DATA / 'answers' / 'history.jsonl'
        history.parent.mkdir(parents=True, exist_ok=True)
        with history.open('a') as f:
            f.write(json.dumps(result) + '\n')
    return result

def answer(question, view='text', dim=768, k=4, use_video=True, use_audio=False):
    return asyncio.run(_answer(question, view, dim, k, use_video, use_audio))
