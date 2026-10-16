import sys
from fastapi.testclient import TestClient
from vrag.api import app

def test_cpu_library():
    with TestClient(app) as c:
        assert c.get('/api/videos').json() == []
        assert c.get('/api/stats').json()['views'] == []
        assert c.get('/api/search?q=test').status_code == 401
        assert c.get('/api/experiments').status_code == 404
    assert not {'torch', 'transformers', 'sentence_transformers', 'vllm'} & sys.modules.keys()

def test_health_and_schema():
    with TestClient(app) as c:
        health = c.get('/api/health').json()
        assert health['inference'] == 'remote-only'
        schema = c.get('/openapi.json').json()
        assert '/api/live/sessions/{sid}/frames' in schema['paths']

def test_config_is_not_public():
    with TestClient(app) as c:
        assert c.get('/api/config').status_code == 401
        assert c.post('/api/live/sessions', json={'consent':True}).status_code == 401
