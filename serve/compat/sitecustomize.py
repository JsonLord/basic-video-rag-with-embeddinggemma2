"""Runtime compatibility shims, auto-imported when this dir is on PYTHONPATH.

vLLM 0.23.0 pulls fastapi 0.137 / starlette 1.3 / prometheus-fastapi-instrumentator
8.0.0 (forced by its `model-hosting-container-standards` dependency — they cannot be
downgraded). That instrumentator's `_get_route_name` does `route.path` for every
route, but vLLM mounts an `_IncludedRouter` route object that has no `.path`, so the
metrics middleware raises `AttributeError: '_IncludedRouter' object has no attribute
'path'` on EVERY request — including /health and /v1/*, making the server unusable.

This patches `_get_route_name` to read the path defensively (getattr) and skip routes
without one. Version-independent and a no-op if the instrumentator isn't installed.
"""


def _patch_prometheus_instrumentator() -> None:
    try:
        from prometheus_fastapi_instrumentator import routing
        from starlette.routing import Match, Mount
    except Exception:
        return

    def _safe_get_route_name(scope, routes, route_name=None):
        for route in routes:
            try:
                match, child_scope = route.matches(scope)
            except Exception:
                continue
            path = getattr(route, "path", None)
            if match == Match.FULL:
                if path is None:
                    return route_name
                route_name = path
                child_scope = {**scope, **child_scope}
                if isinstance(route, Mount) and getattr(route, "routes", None):
                    child = _safe_get_route_name(child_scope, route.routes, route_name)
                    route_name = None if child is None else route_name + child
                return route_name
            elif match == Match.PARTIAL and route_name is None and path is not None:
                route_name = path
        return None

    routing._get_route_name = _safe_get_route_name


_patch_prometheus_instrumentator()
