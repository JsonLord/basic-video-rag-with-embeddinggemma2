"""Measure a CPU container; only creates/removes its own uniquely named container.
Reports CPU app startup/HTTP workload, not live inference. Requires Docker CLI.
"""
import concurrent.futures
import json
import subprocess
import time
import uuid

name='visual-mentor-measure-'+uuid.uuid4().hex[:8]
image='visual-mentor:validation'
def command(*args):
    return subprocess.check_output(args,text=True).strip()
probe="import urllib.request,json; print(json.load(urllib.request.urlopen('http://127.0.0.1:7860/api/health',timeout=2))['status'])"
resource="""
import glob,json,importlib.util
rss=0
for p in glob.glob('/proc/[0-9]*/status'):
 try:
  for line in open(p):
   if line.startswith('VmRSS:'):rss+=int(line.split()[1])*1024
 except OSError:pass
print(json.dumps({'rss_bytes':rss,'forbidden_packages':[m for m in ['torch','transformers','sentence_transformers','vllm'] if importlib.util.find_spec(m)]}))
"""
try:
    start=time.monotonic()
    command('docker','run','-d','--name',name,'--memory=1g','--cpus=2',image)
    for _ in range(100):
        try:
            p = subprocess.run(['docker','exec',name,'python','-c',probe],text=True,capture_output=True)
            if p.returncode == 0 and p.stdout.strip() == 'ok':break
        except subprocess.CalledProcessError:pass
        time.sleep(.1)
    else:raise RuntimeError('container never became healthy')
    ready=time.monotonic()-start
    idle=json.loads(command('docker','exec',name,'python','-c',resource))
    workload="""
import concurrent.futures,urllib.request
paths=['/live','/models','/library','/search','/ask','/api/videos','/api/stats','/api/health','/api/openapi.json']
def request(i):
 path=paths[i%len(paths)]
 try:
  with urllib.request.urlopen('http://127.0.0.1:7860'+path,timeout=15) as r:
   assert r.status==200
   r.read()
 except Exception as e:raise RuntimeError(path+' failed: '+str(e))
with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:list(pool.map(request,range(180)))
print('180 HTTP requests passed')
"""
    result=command('docker','exec',name,'python','-c',workload)
    after=json.loads(command('docker','exec',name,'python','-c',resource))
    peak=int(command('docker','exec',name,'cat','/sys/fs/cgroup/memory.peak'))
    output={'image_id':command('docker','inspect',name,'--format','{{.Image}}'),'image_bytes':int(command('docker','image','inspect',image,'--format','{{.Size}}')),'startup_seconds':round(ready,3),'idle_process_rss_bytes':idle['rss_bytes'],'post_workload_process_rss_bytes':after['rss_bytes'],'cgroup_peak_bytes':peak,'forbidden_packages':idle['forbidden_packages'],'workload':result,'limits':'2 CPUs / 1 GiB; no GPU; no providers configured'}
    print(json.dumps(output,indent=2))
finally:
    subprocess.run(['docker','rm','-f',name],stdout=subprocess.DEVNULL,check=False)
