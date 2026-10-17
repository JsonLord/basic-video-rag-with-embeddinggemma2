"""Measure a CPU container; only creates/removes its own uniquely named container.
Reports CPU app startup/HTTP workload, not live inference. Requires Docker CLI.
"""
import concurrent.futures
import json
import os
import subprocess
import time
import uuid

name='visual-mentor-measure-'+uuid.uuid4().hex[:8]
image=os.environ.get('VM_RUNTIME_IMAGE','visual-mentor:validation')
def command(*args):
    if args[0]=='docker':args=('docker','--host=unix:///var/run/docker.sock',*args[1:])
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
resource = "import json,importlib.util\n" + rss_function + "\nprint(json.dumps({'rss_bytes':app_rss(),'cpu_usage_usec':int(dict(line.split() for line in open('/sys/fs/cgroup/cpu.stat'))['usage_usec']),'forbidden_packages':[m for m in ['torch','transformers','sentence_transformers','vllm'] if importlib.util.find_spec(m)]}))"

try:
    start=time.monotonic()
    command('docker','run','-d','--name',name,'--memory=16g','--cpus=2','--network=none',image)
    for _ in range(100):
        try:
            p = subprocess.run(['docker','--host=unix:///var/run/docker.sock','exec',name,'python','-c',probe],text=True,capture_output=True)
            if p.returncode == 0 and p.stdout.strip() == 'ok':break
        except subprocess.CalledProcessError:pass
        time.sleep(.1)
    else:raise RuntimeError('container never became healthy')
    ready=time.monotonic()-start
    idle=json.loads(command('docker','exec',name,'python','-c',resource))
    workload=rss_function+"""
import concurrent.futures,urllib.request,threading,time,json,subprocess,os
import numpy as np
latencies=[]
ffmpeg_started=time.monotonic()
media=subprocess.Popen(['ffmpeg','-hide_banner','-loglevel','error','-i','/app/web/.next/standalone/public/sample/video.mp4','-vf','scale=480:-2','-c:v','libx264','-threads','1','-preset','veryfast','-y','/tmp/benchmark.mp4'])
rng=np.random.default_rng(0);matrix=rng.normal(size=(10000,768)).astype('float32');matrix/=np.linalg.norm(matrix,axis=1,keepdims=True)
vector=matrix[0].copy()
def numpy_work():
 for _ in range(50):
  scores=matrix@vector
  assert int(np.argmax(scores))==0
stop=threading.Event(); samples=[]
def monitor():
 while not stop.is_set():
  samples.append(app_rss());time.sleep(.025)
thread=threading.Thread(target=monitor);thread.start()
paths=['/live','/models','/','/search','/ask','/api/demo/videos','/api/demo/stats','/api/health','/api/openapi.json']
def request(i):
 started=time.monotonic()
 path=paths[i%len(paths)]
 try:
  with urllib.request.urlopen('http://127.0.0.1:7860'+path,timeout=15) as r:
   assert r.status==200
   r.read()
   latencies.append((time.monotonic()-started)*1000)
 except Exception as e:raise RuntimeError(path+' failed: '+str(e))
try:
 with concurrent.futures.ThreadPoolExecutor(max_workers=5) as pool:
  bench=pool.submit(numpy_work)
  list(pool.map(request,range(180)))
  bench.result()
 assert media.wait(timeout=120)==0
finally:
 stop.set();thread.join()
print(json.dumps({'requests':180,'peak_process_rss_bytes':max(samples),'http_p50_ms':round(float(np.percentile(latencies,50)),2),'http_p95_ms':round(float(np.percentile(latencies,95)),2),'ffmpeg_and_http_elapsed_s':round(time.monotonic()-ffmpeg_started,3),'synthetic_matrix_shape':[10000,768],'matrix_searches':50}))
"""
    workload_started=time.monotonic()
    result=json.loads(command('docker','exec','-e','OPENBLAS_NUM_THREADS=1',name,'python','-c',workload))
    after=json.loads(command('docker','exec',name,'python','-c',resource))
    peak=int(command('docker','exec',name,'cat','/sys/fs/cgroup/memory.peak'))
    output={'image_id':command('docker','inspect',name,'--format','{{.Image}}'),'image_bytes':int(command('docker','image','inspect',image,'--format','{{.Size}}')),'startup_seconds':round(ready,3),'idle_process_rss_bytes':idle['rss_bytes'],'post_workload_process_rss_bytes':after['rss_bytes'],'sampled_peak_process_rss_bytes':max(idle['rss_bytes'],after['rss_bytes'],result['peak_process_rss_bytes']),'cgroup_peak_bytes':peak,'workload_cpu_seconds':round((after['cpu_usage_usec']-idle['cpu_usage_usec'])/1000000,3),'workload_wall_seconds_including_probes':round(time.monotonic()-workload_started,3),'forbidden_packages':idle['forbidden_packages'],'workload':result,'limits':'2 CPUs / 16 GiB; no GPU; no providers configured'}
    print(json.dumps(output,indent=2))
finally:
    subprocess.run(['docker','--host=unix:///var/run/docker.sock','rm','-f',name],stdout=subprocess.DEVNULL,check=False)
