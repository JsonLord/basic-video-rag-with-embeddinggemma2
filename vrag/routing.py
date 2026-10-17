"""Snapshot-based deterministic routing and typed spatial/semantic fusion."""
import asyncio
import time
from config.schema import Configuration
from .providers import Output, ProviderFailure, adapter

async def route(config: Configuration, feature: str, payload: dict, sensitive=True):
    rule = config.features.get(feature)
    if not rule or not rule.enabled:
        raise ProviderFailure('feature_unavailable')
    async def run(name, inp):
        start = time.monotonic()
        try:
            out = await adapter.call(name, config.providers[name], inp, sensitive)
            return out, {'provider': name, 'status': 'ok', 'latency_ms': round((time.monotonic()-start)*1000)}
        except ProviderFailure as exc:
            return None, {'provider': name, 'status': exc.code, 'latency_ms': round((time.monotonic()-start)*1000)}
    names = rule.providers
    if rule.strategy == 'conditional':
        names = [c.provider for c in rule.conditions if (payload.get('camera_id') if c.field == 'camera_id' else bool(payload.get('previous', {}).get('detections'))) == c.equals]
        names = list(dict.fromkeys(names))
    results = []
    outputs = []
    warnings = []
    if rule.strategy == 'parallel':
        tasks = [asyncio.create_task(run(n, payload)) for n in names]
        try:
            for task in asyncio.as_completed(tasks):
                out, status = await task
                results.append(status)
                if out:
                    outputs.append(out)
                if rule.result_policy == 'first_valid' and outputs:
                    break
                if rule.result_policy == 'quorum' and len(outputs) >= rule.quorum:
                    break
        finally:
            for task in tasks:
                if not task.done():
                    task.cancel()
            await asyncio.gather(*tasks, return_exceptions=True)
        called = {r['provider'] for r in results}
        results.extend({'provider': n, 'status': 'cancelled', 'latency_ms': 0} for n in names if n not in called)
        if rule.result_policy == 'quorum' and len(outputs) < rule.quorum:
            outputs = []
            warnings.append('quorum_not_met')
    else:
        inp = dict(payload)
        for n in names:
            out, status = await run(n, inp)
            results.append(status)
            if out:
                outputs.append(out)
                if rule.strategy == 'fallback':
                    break
                if rule.strategy == 'sequential':
                    inp['previous'] = out.model_dump(exclude_none=True)
            elif rule.strategy == 'sequential' or rule.strategy == 'fallback' and status['status'] not in rule.fallback_on:
                break
    # Boxes can ONLY originate from a validated detector adapter. No text-to-box conversion.
    merged = Output(
        warnings=warnings,
        detections=[d for o in outputs for d in o.detections][:200],
        decisions=[d for o in outputs for d in o.decisions][:20],
        text='\n'.join(o.text for o in outputs if o.text)[:32000],
        embedding=next((o.embedding for o in outputs if o.embedding), None),
    )
    return merged, results
