"""Offline CPU/container and authorization qualification; publishes no ports.
Creates only uniquely named test containers/volumes, and removes them on exit.
"""
import argparse
import json
import os
import secrets
import subprocess
import time
import uuid

parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--image',default='visual-mentor:release-review')
args=parser.parse_args()
name='vm-release-'+uuid.uuid4().hex[:10]
volume=name+'-state'
process_env=os.environ.copy()
for variable in ['DOCKER_HOST','DOCKER_CONTEXT','DOCKER_TLS','DOCKER_TLS_VERIFY','DOCKER_CERT_PATH']:
    process_env.pop(variable,None)
process_env.update(VM_ADMIN_TOKEN=secrets.token_urlsafe(32),VM_USER_TOKEN=secrets.token_urlsafe(32))

def docker(*arguments):
    return subprocess.check_output(['docker','--host=unix:///var/run/docker.sock',*arguments],env=process_env,text=True).strip()

def start():
    docker('run','-d','--name',name,'--network','none','--memory=16g','--cpus=2',
        '--mount',f'type=volume,src={volume},dst=/app/data',
        '-e','VM_ADMIN_TOKEN','-e','VM_USER_TOKEN','-e','VM_STATE_DIR=/app/data/state',
        '-e','VM_ALLOWED_ORIGINS=https://private-release.example',args.image)
    for _ in range(100):
        ready=subprocess.run(['docker','--host=unix:///var/run/docker.sock','exec',name,'python','-c',
            "import urllib.request; assert urllib.request.urlopen('http://127.0.0.1:7860/api/health',timeout=2).status==200"],
            env=process_env,capture_output=True,timeout=5)
        if ready.returncode==0:return
        time.sleep(.1)
    raise RuntimeError('container did not become healthy')

checks=r'''
import base64,glob,importlib.util,io,json,os,urllib.request,urllib.error
from PIL import Image
base='http://127.0.0.1:7860'
a=os.environ['VM_ADMIN_TOKEN'];u=os.environ['VM_USER_TOKEN']
results={}
def call(path,method='GET',body=None,token=None,headers=None):
 h=dict(headers or {})
 if token:h['Authorization']='Bearer '+token
 if body is not None:h['Content-Type']='application/json'
 request=urllib.request.Request(base+path,method=method,data=json.dumps(body).encode() if body is not None else None,headers=h)
 try:
  with urllib.request.urlopen(request,timeout=15) as r:return r.status,r.read()
 except urllib.error.HTTPError as e:return e.code,e.read()
assert call('/api/health')[0]==200
assert call('/api/videos')[0]==401
assert call('/api/demo/videos')[0]==200
from pathlib import Path
media=Path('/app/data/videos/qualification');media.mkdir(parents=True,exist_ok=True)
source=Path('/app/web/.next/standalone/public/sample/video.mp4').read_bytes()
(media/'video.mp4').write_bytes(source)
assert call('/media/qualification/video.mp4')[0]==401
assert call('/media/qualification/video.mp4',token=a)[0]==401
status,raw=call('/media/qualification/video.mp4',token=u,headers={'Range':'bytes=0-31'})
assert status==206 and raw==source[:32]
status,raw=call('/media/qualification/video.mp4',headers={'Cookie':'vm-media='+u,'Range':'bytes=32-63'})
assert status==206 and raw==source[32:64]

assert call('/media/private/video.mp4')[0]==401
assert call('/api/admin/backup-status')[0]==401
for path in ['/api/config','/api/config/template','/api/config/profiles']:
 assert call(path)[0]==401 and call(path,token=u)[0]==401
for path,body in [('/api/config/validate',{'yaml':'{}'}),('/api/config/apply',{'yaml':'{}'}),('/api/config/rollback',{'version':1,'expected_version':1}),('/api/providers/missing/test',{}),('/api/routing/dry-run',{'feature':'live.camera1.scene'})]:
 assert call(path,'POST',body,u)[0]==401
assert call('/api/config','GET',token=a)[0]==200
assert call('/api/config/apply','POST',{'yaml':'profile: reject'},a,{'Origin':'https://evil.example','X-Forwarded-Host':'evil.example'})[0]==403
assert call('/api/live/sessions','POST',{'consent':True})[0]==401
assert call('/api/live/sessions','POST',{'consent':False},u)[0]==400
status,raw=call('/api/config/apply','POST',{'yaml':'profile: release-qualification','expected_version':1},a,{'Origin':'https://private-release.example'})
assert status==200 and json.loads(raw)['config_version']==2
status,raw=call('/api/config','GET',token=a)
assert a.encode() not in raw and u.encode() not in raw
assert call('/api/config/apply','POST',{'yaml':'profile: stale','expected_version':1},a)[0]==409
status,raw=call('/api/live/sessions','POST',{'consent':True},u);assert status==200
sid=json.loads(raw)['session_id']
assert call('/api/live/sessions/'+sid+'/events','GET',token=a)[0]==401
f=io.BytesIO();Image.new('RGB',(32,32)).save(f,format='JPEG')
frame={'camera_id':'camera1','frame_id':1,'captured_at':1,'image':'data:image/jpeg;base64,'+base64.b64encode(f.getvalue()).decode(),'feature':'live.camera1.scene','config_version':2,'request_id':'synthetic'}
status,raw=call('/api/live/sessions/'+sid+'/frames','POST',frame,u)
assert status==503 and json.loads(raw)['detail']=='feature_unavailable'
assert call('/api/live/sessions/'+sid,'DELETE',token=u)[0]==200
assert call('/api/live/sessions/'+sid+'/events','GET',token=u)[0]==404
assert call('/api/config/rollback','POST',{'version':1,'expected_version':2},a)[0]==200
assert call('/api/config/apply','POST',{'yaml':'profile: release-qualification','expected_version':3},a)[0]==200
packages=['torch','torchvision','torchaudio','torchcodec','transformers','sentence_transformers','vllm','whisper','onnxruntime','huggingface_hub']
installed=[p for p in packages if importlib.util.find_spec(p)]
assert not installed and not glob.glob('/dev/nvidia*')
weights=[]
for root in ['/app','/home/mentor']:
 for suffix in ['*.safetensors','*.onnx','*.gguf','*.pt']:
  weights.extend(glob.glob(root+'/**/'+suffix,recursive=True))
assert not weights
assert os.getuid()==1000
results.update(media_range_and_cookie='passed',authentication='passed',csrf_origin='passed',config_apply_rollback='passed',session_ownership='passed',disabled_inference='503 without local fallback',uid=os.getuid(),forbidden_packages=installed,model_weights=weights,gpu_devices=[])
print(json.dumps(results))
'''
try:
    docker('volume','create',volume)
    start_time=time.monotonic();start();startup=round(time.monotonic()-start_time,3)
    result=json.loads(docker('exec',name,'python','-c',checks))
    container=json.loads(docker('inspect',name))[0]
    assert not container['HostConfig']['PortBindings']
    assert container['HostConfig']['NetworkMode']=='none'
    assert not container['HostConfig'].get('DeviceRequests')
    image_id=container['Image']
    docker('rm','-f',name)
    start()
    persistence=json.loads(docker('exec',name,'python','-c',"import json,os,urllib.request; r=urllib.request.Request('http://127.0.0.1:7860/api/config',headers={'Authorization':'Bearer '+os.environ['VM_ADMIN_TOKEN']}); data=json.load(urllib.request.urlopen(r)); assert data['config_version']==4 and data['config']['profile']=='release-qualification'; print(json.dumps({'recreated_container_config_version':4}))"))
    print(json.dumps({'image_id':image_id,'startup_seconds':startup,'network':'none','published_ports':[],
        'limits':'2 CPUs / 16 GiB','checks':result,'persistent_volume':persistence},indent=2))
finally:
    subprocess.run(['docker','--host=unix:///var/run/docker.sock','rm','-f',name],env=process_env,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
    subprocess.run(['docker','--host=unix:///var/run/docker.sock','volume','rm',volume],env=process_env,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
