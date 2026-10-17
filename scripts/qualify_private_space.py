"""Private staging boundary probe; optional bounded checkpoint trigger. No deployment."""
import argparse
import json
import os
from pathlib import Path
import re
import time
from urllib.parse import urlsplit
import httpx
try:
    from .coordinate_backup import coordinate
except ImportError:
    from coordinate_backup import coordinate


def qualify(client, space, url, hf, trigger, run_trigger=False):
    parsed=urlsplit(url)
    if space=='Leon4gr45/openweb' or not re.fullmatch(r'[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]*staging[A-Za-z0-9_.-]*',space):
        raise ValueError('only a separate staging Space is permitted')
    if parsed.scheme!='https' or not parsed.hostname or not parsed.hostname.endswith('.hf.space') or parsed.path or parsed.query or parsed.fragment or parsed.port or parsed.username:
        raise ValueError('dedicated HTTPS Space origin required')
    if len(trigger)<32:raise ValueError('staging trigger token must be >=32 characters')
    bearer={'Authorization':'Bearer '+hf}
    response=client.get('https://huggingface.co/api/spaces/'+space,headers=bearer)
    response.raise_for_status();metadata=response.json()
    report={'space':space,'origin':url,'private':metadata.get('private'),
            'initial_runtime_stage':metadata.get('runtime',{}).get('stage'),'sleep_wake_verified':False,
            'actions_runner':bool(os.environ.get('GITHUB_ACTIONS')=='true'),
            'actions_run_url':f"https://github.com/{os.environ['GITHUB_REPOSITORY']}/actions/runs/{os.environ['GITHUB_RUN_ID']}" if os.environ.get('GITHUB_ACTIONS')=='true' else None}
    if report['private'] is not True:raise ValueError('Space is not private')
    endpoint=url+'/api/admin/backup-status'
    # Authenticated status access is the approved natural wake route; no
    # restart/resume/hardware request is made. Reject credential failures early.
    for attempt in range(40):
        authorized=client.get(endpoint,headers={**bearer,'X-VM-Backup-Token':trigger})
        if authorized.status_code not in (502,503,504):break
        time.sleep(15)
    report['authorized_status']=authorized.status_code
    if authorized.status_code!=200 or not authorized.json().get('configured'):raise ValueError('authorized configured backup route not established')
    anonymous=client.get(endpoint)
    wrong=client.get(endpoint,headers={**bearer,'X-VM-Backup-Token':'invalid-staging-test-token'})
    report.update(anonymous_status=anonymous.status_code,wrong_trigger_status=wrong.status_code)
    if anonymous.status_code not in (301,302,303,307,308,401,403,404):raise ValueError('anonymous denial not established')
    if wrong.status_code not in (401,403):raise ValueError('wrong trigger token was not rejected at the application')
    report.update(private_boundary_verified=True,checkpoint_triggered=False)
    if run_trigger:
        os.environ.update(VM_SPACE_ID=space,VM_SPACE_URL=url)
        result=coordinate(client)
        report.update(checkpoint_triggered=True,checkpoint=result['checkpoint'],checkpoint_verified=result['verified'])
        report['sleep_wake_verified']=report['initial_runtime_stage'] in ('SLEEPING','SLEEPING_RESOURCE')
    return report


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--space',required=True);parser.add_argument('--url',required=True);parser.add_argument('--trigger',action='store_true')
    args=parser.parse_args()
    events=[]
    def observed(response):
        events.append({'method':response.request.method,'host':response.request.url.host,
                       'status':response.status_code,'request_id':response.headers.get('x-request-id')})
    report={'status':'blocked','private_boundary_verified':False,'checkpoint_verified':False,'sleep_wake_verified':False}
    try:
        hf=os.environ['HF_SPACE_TOKEN'];trigger=os.environ['VM_BACKUP_TRIGGER_TOKEN']
        with httpx.Client(timeout=30,follow_redirects=False,event_hooks={'response':[observed]}) as client:
            report=qualify(client,args.space,args.url,hf,trigger,args.trigger)
        report['status']='passed'
    except KeyError:report['failure_code']='missing_secure_staging_credentials'
    except Exception:report['failure_code']='private_staging_qualification_failed'
    report['http_events']=events
    evidence=Path('docs/evidence/private-staging-live.json');evidence.parent.mkdir(parents=True,exist_ok=True)
    evidence.write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report))
    raise SystemExit(0 if report['status']=='passed' else 2)
