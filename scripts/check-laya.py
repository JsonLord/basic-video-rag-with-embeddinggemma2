"""Read Laya metadata; --synthetic additionally sends one generated test image.
Never captures a camera, reads personal media, or prints credentials.
"""
import argparse
import asyncio
import base64
import io
import json
import os
from pathlib import Path
import sys
import time

sys.path.insert(0,str(Path(__file__).resolve().parent.parent))
import httpx
from PIL import Image
from config.schema import Provider
from vrag.egress import transport_for
from vrag.providers import Adapter, MAX_RESPONSE, destination

async def check(synthetic):
    p=Provider(adapter='laya-vision',base_url_env='LAYA_BASE_URL',
        api_key_secret='LAYA_API_KEY' if os.environ.get('LAYA_API_KEY') else None,
        model='thaitea/laya-vision',capabilities=['image_understanding','visual_decision'],
        trust='approved_sensitive',timeout_ms=60000,concurrency=1)
    base=await destination(p,False)
    headers={'Authorization':'Bearer '+os.environ[p.api_key_secret]} if p.api_key_secret else {}
    metadata={}
    async with httpx.AsyncClient(transport=transport_for(base),follow_redirects=False,timeout=15) as client:
        for path in ['/health','/ready','/v1/info']:
            async with client.stream('GET',base+path,headers=headers) as r:
                if r.status_code!=200:raise RuntimeError(f'{path}: HTTP {r.status_code}')
                body=bytearray()
                async for chunk in r.aiter_bytes():
                    body.extend(chunk)
                    if len(body)>MAX_RESPONSE:raise RuntimeError('metadata response too large')
                metadata[path]=json.loads(body)
    output={'metadata':metadata,'authenticated':bool(p.api_key_secret),'synthetic_inference_executed':False}
    if synthetic:
        image=io.BytesIO();Image.new('RGB',(64,64),'white').save(image,format='JPEG')
        start=time.monotonic()
        result=await Adapter().call('laya',p,{
            'image':'data:image/jpeg;base64,'+base64.b64encode(image.getvalue()).decode(),
            'text':'Synthetic Visual Mentor release connection test. No camera or personal data.',
            'frame_id':0,'camera_id':'synthetic'})
        output.update(synthetic_inference_executed=True,elapsed_s=round(time.monotonic()-start,3),output=result.model_dump())
    return output

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--synthetic',action='store_true',help='Explicitly send one generated image for inference')
    args=parser.parse_args()
    print(json.dumps(asyncio.run(check(args.synthetic)),indent=2))
