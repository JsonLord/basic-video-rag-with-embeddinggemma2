"""Bounded private-Space probe and checkpoint coordinator. Never restarts a Space."""
import os
import time
from urllib.parse import urlsplit
import httpx


def coordinate(client, sleep=time.sleep, clock=time.time):
    target=os.environ['VM_SPACE_URL'].rstrip('/')
    parsed=urlsplit(target)
    if parsed.scheme!='https' or not parsed.hostname or not parsed.hostname.endswith('.hf.space') or parsed.path or parsed.query or parsed.fragment or parsed.port or parsed.username:
        raise ValueError('expected a dedicated HTTPS hf.space origin')
    space=os.environ['VM_SPACE_ID']
    import re
    if not re.fullmatch(r'[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+',space):raise ValueError('invalid Space identity')
    hf=os.environ['HF_SPACE_TOKEN'];trigger=os.environ['VM_BACKUP_TRIGGER_TOKEN']
    if len(trigger)<32:raise ValueError('trigger token must have at least 32 characters')
    hfheaders={'Authorization':'Bearer '+hf}
    metadata=client.get('https://huggingface.co/api/spaces/'+space,headers=hfheaders)
    metadata.raise_for_status()
    if metadata.json().get('private') is not True:raise ValueError('Space privacy not verified')
    headers={**hfheaders,'X-VM-Backup-Token':trigger}
    # HTTP access may wake a sleeping private Space; only a successful protected
    # endpoint response proves it for the configured destination.
    for attempt in range(40):
        try:
            response=client.get(target+'/api/admin/backup-status',headers=headers)
            if response.status_code==200 and response.json().get('configured'):break
            if response.status_code in (401,403,404):raise ValueError('private Space route/authentication inaccessible')
        except (httpx.TimeoutException,httpx.NetworkError):pass
        sleep(15)
    else:raise ValueError('private Space did not become reachable within ten minutes')
    before=response.json().get('last_success')
    result=client.post(target+'/api/admin/backup',headers=headers,json={});result.raise_for_status()
    if result.json().get('accepted') is not True:raise ValueError('checkpoint not accepted')
    started=clock()
    for attempt in range(120):
        sleep(10)
        status=client.get(target+'/api/admin/backup-status',headers=headers);status.raise_for_status();report=status.json()
        if report.get('failure_code'):raise ValueError('Space reported backup failure')
        latest=report.get('last_success')
        if latest and latest!=before and latest.get('created_at',0)>=started-10:
            return {'verified':True,'checkpoint':latest['checkpoint'],'private_route_verified':True}
    raise ValueError('accepted checkpoint did not complete in twenty minutes')


if __name__=='__main__':
    with httpx.Client(timeout=30,follow_redirects=False) as client:
        # Print only safe operational metadata, never remote error bodies/tokens.
        try:
            import json
            print(json.dumps(coordinate(client)))
        except Exception:
            raise SystemExit('Coordinator failed: verify private routing, wake capability, authentication and backup health. No scheduling success established.') from None
