#!/usr/bin/env python3
"""Standalone release probe: Python stdlib + age/age-keygen; no app imports.

Only VM_BACKUP_GITHUB_TOKEN is read for authentication. Existing releases and
checkpoints are never changed. Each run creates at most one new test release.
"""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import ssl
import subprocess
import tempfile
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode, urlsplit
from urllib.request import HTTPRedirectHandler, HTTPSHandler, Request, build_opener
import uuid

LIMIT = 1024 * 1024


class Failure(Exception):
    pass


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


class Probe:
    def __init__(self, repo, token, report, save):
        self.repo, self.token, self.report, self.save = repo, token, report, save
        self.base = 'https://api.github.com/repos/' + repo
        # Preserve the machine's approved proxy settings and CA trust.
        context = ssl.create_default_context(cafile=os.environ.get('SSL_CERT_FILE') or None)
        self.opener = build_opener(NoRedirect(), HTTPSHandler(context=context))

    def request(self, method, url, data=None, authenticated=True, redirect=False):
        parsed = urlsplit(url)
        hosts = ('api.github.com', 'uploads.github.com') if authenticated else (
            'release-assets.githubusercontent.com', 'objects.githubusercontent.com')
        if (parsed.scheme != 'https' or parsed.hostname not in hosts
                or parsed.username or parsed.password or parsed.port not in (None, 443)
                or parsed.fragment):
            raise Failure('destination_denied')
        headers = {'Accept': 'application/vnd.github+json', 'User-Agent': 'vm-release-credential-probe',
                   'X-GitHub-Api-Version': '2022-11-28'}
        if authenticated:
            headers['Authorization'] = 'Bearer ' + self.token
        if isinstance(data, dict):
            data = json.dumps(data).encode()
            headers['Content-Type'] = 'application/json'
        elif data is not None:
            headers['Content-Type'] = 'application/octet-stream'
        if '/releases/assets/' in parsed.path or not authenticated:
            headers['Accept'] = 'application/octet-stream'
        try:
            response = self.opener.open(Request(url, data=data, headers=headers, method=method), timeout=30)
        except HTTPError as error:
            response = error  # Record response metadata only; never print its URL/body.
        except (URLError, OSError):
            raise Failure('network_or_tls_failure') from None
        with response:
            status = response.code
            event = {'host': parsed.hostname, 'method': method, 'status': status,
                     'request_id': response.headers.get('X-GitHub-Request-Id'),
                     'authenticated': authenticated,
                     'accepted_permissions': response.headers.get('X-Accepted-GitHub-Permissions')}
            self.report['http_events'].append(event)
            self.save()
            if redirect and status in (301, 302, 303, 307, 308):
                return status, b'', response.headers.get('Location', '')
            if not 200 <= status < 300:
                # No retries, including 401/403/404: preserve the first rejection.
                raise Failure('authentication_rejected' if status == 401 else 'http_rejected_' + str(status))
            body = response.read(LIMIT + 1)
            if len(body) > LIMIT:
                raise Failure('response_too_large')
            return status, body, None

    def json_request(self, method, url, data=None):
        status, body, _ = self.request(method, url, data)
        try:
            return status, json.loads(body)
        except (ValueError, UnicodeError):
            raise Failure('invalid_json_response') from None

    def run(self, ciphertext, run_id):
        self.report.update(ciphertext_bytes=len(ciphertext),
                           expected_sha256=hashlib.sha256(ciphertext).hexdigest())
        self.save()
        _, repo = self.json_request('GET', self.base)
        if repo.get('private') is not True:
            raise Failure('repository_not_private')
        self.report['private_repository_verified'] = True
        push = repo.get('permissions', {}).get('push')
        self.report['repository_push_permission_reported'] = push
        if push is False:
            raise Failure('repository_write_permission_denied')
        tag = 'vm-credential-test-' + run_id
        status, release = self.json_request('POST', self.base + '/releases', {
            'tag_name': tag, 'name': tag, 'prerelease': True, 'draft': False,
            'body': 'Disposable synthetic encrypted credential probe. No application data.'})
        if status != 201:
            raise Failure('release_creation_not_confirmed')
        release_id = release.get('id')
        if not isinstance(release_id, int) or isinstance(release_id, bool) or release_id <= 0:
            raise Failure('invalid_release_id')
        self.report.update(release_id=release_id, release_tag=tag, contents_write_verified=True)
        self.save()  # Successful release creation is an actual Contents-write operation.
        upload = release.get('upload_url', '').split('{', 1)[0]
        parsed = urlsplit(upload)
        expected = '/repos/' + self.repo + '/releases/' + str(release_id) + '/assets'
        if (parsed.scheme != 'https' or parsed.hostname != 'uploads.github.com'
                or parsed.path != expected or parsed.query or parsed.fragment
                or parsed.username or parsed.password or parsed.port not in (None, 443)):
            raise Failure('upload_url_denied')
        status, asset = self.json_request('POST', upload + '?' + urlencode({'name': 'synthetic.age'}), ciphertext)
        if status != 201:
            raise Failure('asset_creation_not_confirmed')
        asset_id = asset.get('id')
        if not isinstance(asset_id, int) or isinstance(asset_id, bool) or asset_id <= 0:
            raise Failure('invalid_asset_id')
        self.report['asset_id'] = asset_id
        self.save()
        status, downloaded, location = self.request('GET', self.base + '/releases/assets/' + str(asset_id), redirect=True)
        if location is not None:
            _, downloaded, _ = self.request('GET', location, authenticated=False)
        expected_hash = hashlib.sha256(ciphertext).hexdigest()
        actual_hash = hashlib.sha256(downloaded).hexdigest()
        self.report.update(ciphertext_bytes=len(ciphertext), expected_sha256=expected_hash,
                           downloaded_sha256=actual_hash)
        if actual_hash != expected_hash or len(downloaded) != len(ciphertext):
            raise Failure('asset_readback_mismatch')
        self.report.update(asset_readback_verified=True, upload_decision='GO',
                           staging_decision='NO-GO: complete recovery and private HF qualification still required',
                           status='passed')


def encrypt_fixture(age, keygen):
    with tempfile.TemporaryDirectory(prefix='vm-release-probe-') as scratch:
        root = Path(scratch)
        identity, clear, encrypted = root / 'identity.agekey', root / 'synthetic.txt', root / 'synthetic.age'
        def command(args):
            try:
                result = subprocess.run(args, capture_output=True, timeout=30)
            except (OSError, subprocess.TimeoutExpired):
                raise Failure('age_tool_failed') from None
            if result.returncode:
                raise Failure('age_tool_failed')
            return result.stdout
        command([keygen, '-o', str(identity)])
        identity.chmod(0o600)
        recipient = command([keygen, '-y', str(identity)]).decode().strip()
        payload = b'Visual Mentor synthetic release credential qualification; no user data.\n'
        clear.write_bytes(payload)
        command([age, '-r', recipient, '-o', str(encrypted), str(clear)])
        if command([age, '-d', '-i', str(identity), str(encrypted)]) != payload:
            raise Failure('local_age_roundtrip_failed')
        ciphertext = encrypted.read_bytes()
        if not ciphertext.startswith(b'age-encryption.org/v1') or len(ciphertext) >= LIMIT:
            raise Failure('invalid_encrypted_fixture')
        return ciphertext  # The disposable test key is destroyed on exit.


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--repo', default='JsonLord/visual-mentor-backups')
    parser.add_argument('--output', type=Path, help='New evidence file; existing files are refused')
    parser.add_argument('--age', default='age', help='age executable path')
    parser.add_argument('--age-keygen', default='age-keygen', help='age-keygen executable path')
    args = parser.parse_args()
    if not re.fullmatch(r'[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+', args.repo):
        parser.error('invalid owner/repository')
    run_id = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ') + '-' + uuid.uuid4().hex
    output = args.output or Path('github-release-qualification-' + run_id + '.json')
    report = {'run_id': run_id, 'repository': args.repo, 'credential_source': 'VM_BACKUP_GITHUB_TOKEN',
              'status': 'started', 'upload_decision': 'NO-GO', 'staging_decision': 'NO-GO',
              'contents_write_verified': False, 'asset_readback_verified': False, 'http_events': [],
              'recovery_run': False, 'production_or_workflows_changed': False}
    # Exclusive creation protects all previous evidence. Only this run's new file is updated.
    try:
        with output.open('x', encoding='utf-8') as stream:
            stream.write(json.dumps(report, indent=2) + '\n')
        output.chmod(0o600)
    except OSError:
        print('NO-GO: evidence path unavailable or already exists; no requests made.')
        return 2
    def save():
        output.write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
    try:
        token = os.environ.get('VM_BACKUP_GITHUB_TOKEN')
        if not token:
            raise Failure('dedicated_credential_missing')
        age, keygen = shutil.which(args.age), shutil.which(args.age_keygen)
        if not age or not keygen:
            raise Failure('install_age_and_age_keygen')
        ciphertext = encrypt_fixture(age, keygen)
        report['local_age_roundtrip_verified'] = True
        Probe(args.repo, token, report, save).run(ciphertext, run_id)
    except Failure as error:
        report.update(status='failed', failure_code=str(error))
    except Exception:
        report.update(status='failed', failure_code='unexpected_local_failure')
    save()
    print(json.dumps({'status': report['status'], 'upload_decision': report['upload_decision'],
                      'evidence': str(output), 'failure_code': report.get('failure_code'),
                      'asset_id': report.get('asset_id')}))
    return 0 if report['status'] == 'passed' else 2


if __name__ == '__main__':
    raise SystemExit(main())
