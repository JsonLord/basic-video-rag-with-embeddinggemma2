import sys
from fastapi.testclient import TestClient
from vrag.api import app

def test_cpu_library():
    with TestClient(app) as c:
        assert c.get('/api/videos').json() == []
        assert c.get('/api/stats').json()['views'] == []
        assert c.get('/api/search?q=test').status_code == 400
        assert c.get('/api/experiments').status_code == 404
    assert not {'torch', 'transformers', 'sentence_transformers', 'vllm'} & sys.modules.keys()
