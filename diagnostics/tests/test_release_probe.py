import hashlib
import importlib.util
import io
import json
from pathlib import Path
import tempfile
import unittest
from urllib.error import HTTPError
from unittest.mock import patch

spec = importlib.util.spec_from_file_location('probe', Path(__file__).parents[1] / 'qualify_github_release.py')
probe = importlib.util.module_from_spec(spec)
spec.loader.exec_module(probe)


class Response(io.BytesIO):
    def __init__(self, code, body=b'', headers=None):
        super().__init__(body)
        self.code, self.headers = code, headers or {'X-GitHub-Request-Id': 'TEST:SAFE'}


class ProbeTests(unittest.TestCase):
    def make(self):
        report = {'http_events': []}
        return probe.Probe('test/private', 'secret-never-log', report, lambda: None), report

    def test_roundtrip_and_stripped_signed_download(self):
        client, report = self.make()
        ciphertext = b'age-encryption.org/v1\nsynthetic mock ciphertext'
        requests = []
        class Opener:
            def open(self, req, timeout):
                requests.append(req)
                url, method = req.full_url, req.get_method()
                if url == client.base:
                    return Response(200, json.dumps({'private': True, 'permissions': {'push': True}}).encode())
                if url.endswith('/releases'):
                    return Response(201, json.dumps({'id': 9, 'upload_url': 'https://uploads.github.com/repos/test/private/releases/9/assets{?name,label}'}).encode())
                if 'uploads.github.com' in url:
                    self.uploaded = req.data
                    return Response(201, b'{"id":19}')
                if '/releases/assets/19' in url:
                    return Response(302, headers={'Location': 'https://release-assets.githubusercontent.com/object?signature=not-recorded'})
                assert req.get_header('Authorization') is None
                return Response(200, self.uploaded)
        client.opener = Opener()
        client.run(ciphertext, 'unique')
        self.assertTrue(report['contents_write_verified'])
        self.assertTrue(report['asset_readback_verified'])
        self.assertEqual(report['downloaded_sha256'], hashlib.sha256(ciphertext).hexdigest())
        self.assertEqual(report['asset_id'], 19)
        self.assertEqual(len(requests), 5)
        self.assertNotIn('secret-never-log', json.dumps(report))
        self.assertNotIn('signature', json.dumps(report))
        self.assertEqual(sum(r.get_method() == 'POST' and r.full_url.endswith('/releases') for r in requests), 1)

    def test_permanent_failure_stops_without_retry(self):
        for status in (401, 403, 404, 422):
            client, report = self.make()
            calls = []
            class Opener:
                def open(self, req, timeout):
                    calls.append(req)
                    raise HTTPError(req.full_url, status, 'redacted', {'X-GitHub-Request-Id': 'REJECT'}, io.BytesIO(b'never-record-this-body'))
            client.opener = Opener()
            with self.assertRaises(probe.Failure):
                client.request('POST', 'https://uploads.github.com/endpoint', b'encrypted')
            self.assertEqual(len(calls), 1)
            self.assertEqual(report['http_events'][0]['status'], status)
            self.assertNotIn('never-record', json.dumps(report))

    def test_untrusted_destination_rejected_before_request(self):
        client, _ = self.make()
        class Forbidden:
            def open(self, *args, **kwargs):
                raise AssertionError('must not send')
        client.opener = Forbidden()
        for url in ('http://api.github.com/private', 'https://evil.example/private', 'https://token@api.github.com/private'):
            with self.assertRaises(probe.Failure):
                client.request('GET', url)

    def test_missing_dedicated_token_does_not_use_integration_token(self):
        with tempfile.TemporaryDirectory() as root:
            output = Path(root) / 'new.json'
            with patch.dict(probe.os.environ, {'GH_TOKEN': 'never-use'}, clear=True), patch('sys.argv', ['probe', '--output', str(output)]), patch('builtins.print'):
                self.assertEqual(probe.main(), 2)
            self.assertEqual(json.loads(output.read_text())['failure_code'], 'dedicated_credential_missing')
            original = output.read_bytes()
            with patch('sys.argv', ['probe', '--output', str(output)]), patch('builtins.print'):
                self.assertEqual(probe.main(), 2)
            self.assertEqual(output.read_bytes(), original)


if __name__ == '__main__':
    unittest.main()
