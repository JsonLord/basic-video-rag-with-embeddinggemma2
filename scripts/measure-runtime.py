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
rss_function = """
def app_rss():
 import glob
 processes={}
 for p in glob.glob('/proc/[0-9]*/status'):
  try:
   fields={line.split(':',1)[0]:line.split(':',1)[1].strip() for line in open(p) if ':' in line}
   processes[int(fields['Pid'])]=(int(fields['PPid']),int(fields.get('VmRSS','0 kB').split()[0])*1024)
  except (OSError,ValueError):pass
 included={1}
 for _ in range(10):
  included.update(pid for pid,(parent,rss) in processes.items() if parent in included)
 return sum(rss for pid,(parent,rss) in processes.items() if pid in included)
"""
resource = "import json,importlib.util\n" + rss_function + "\nprint(json.dumps({'rss_bytes':app_rss(),'forbidden_packages':[m for m in ['torch','transformers','sentence_transformers','vllm'] if importlib.util.find_spec(m)]}))"

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
    workload=rss_function+"""
import concurrent.futures,urllib.request,threading,time,json
stop=threading.Event(); samples=[]
def monitor():
 while not stop.is_set():
  samples.append(app_rss());time.sleep(.025)
thread=threading.Thread(target=monitor);thread.start()
paths=['/live','/models','/library','/search','/ask','/api/videos','/api/stats','/api/health','/api/openapi.json']
def request(i):
 path=paths[i%len(paths)]
 try:
  with urllib.request.urlopen('http://127.0.0.1:7860'+path,timeout=15) as r:
   assert r.status==200
   r.read()
 except Exception as e:raise RuntimeError(path+' failed: '+str(e))
with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:list(pool.map(request,range(180)))
stop.set();thread.join()
print(json.dumps({'requests':180,'peak_process_rss_bytes':max(samples)}))
"""
    result=json.loads(command('docker','exec',name,'python','-c',workload))
    after=json.loads(command('docker','exec',name,'python','-c',resource))
    peak=int(command('docker','exec',name,'cat','/sys/fs/cgroup/memory.peak'))
    output={'image_id':command('docker','inspect',name,'--format','{{.Image}}'),'image_bytes':int(command('docker','image','inspect',image,'--format','{{.Size}}')),'startup_seconds':round(ready,3),'idle_process_rss_bytes':idle['rss_bytes'],'post_workload_process_rss_bytes':after['rss_bytes'],'sampled_peak_process_rss_bytes':max(idle['rss_bytes'],after['rss_bytes'],result['peak_process_rss_bytes']),'cgroup_peak_bytes':peak,'forbidden_packages':idle['forbidden_packages'],'workload':result,'limits':'2 CPUs / 1 GiB; no GPU; no providers configured'}
    print(json.dumps(output,indent=2))
finally:
    subprocess.run(['docker','rm','-f',name],stdout=subprocess.DEVNULL,check=False)
