import requests,json,concurrent.futures
from pathlib import Path
from urllib.parse import urljoin
P=Path('film-discovery/oha-live');headers={'User-Agent':'Mozilla/5.0'}
def run(f):
 d=json.loads(f.read_text(encoding='utf-8'))
 for v in d.get('variants',[]):
  if not v.get('hls'):continue
  try:
   data=requests.get('https://oha.to/live/resolve',params={'url':v['pageUrl']},timeout=12).json();url=data['url'];r=requests.get(url,headers=headers,timeout=12);r.raise_for_status();text=r.text
   if '#EXT-X-STREAM-INF' in text:
    variant=next(l.strip()for l in text.splitlines()if l.strip()and not l.startswith('#'));url=urljoin(url,variant);r=requests.get(url,headers=headers,timeout=12);r.raise_for_status();text=r.text
   segment=next(l.strip()for l in text.splitlines()if l.strip()and not l.startswith('#'))
   with requests.get(urljoin(url,segment),headers=dict(headers,Range='bytes=0-187'),timeout=12,stream=True)as r:
    v['segmentHttp']=r.status_code;v['segmentAccessible']=r.status_code in (200,206)and bool(r.raw.read(188))
   if v['segmentAccessible']:break
  except Exception as e:v['segmentError']=type(e).__name__
 f.write_text(json.dumps(d,ensure_ascii=False,indent=2),encoding='utf-8');print(d['name'],any(v.get('segmentAccessible')for v in d.get('variants',[])),flush=True)
files=[f for f in P.glob('*.json')if f.name!='app-group.json']
with concurrent.futures.ThreadPoolExecutor(max_workers=3)as p:list(p.map(run,files))
