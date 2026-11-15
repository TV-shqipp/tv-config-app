import json,requests,concurrent.futures,re
from pathlib import Path
from urllib.parse import urljoin
P=Path('series-catalog');metadata={}
for root in [P/'expansion',P/'research']:
 for f in root.glob('*season-*.json'):
  d=json.loads(f.read_text(encoding='utf-8'));es=d.get('items',[]) if isinstance(d,dict) else []
  for e in es:
   if e.get('handle') and e.get('videoExternalId'):metadata[e['handle']]=e
cfg=json.loads(Path('app/src/main/assets/config.json').read_text(encoding='utf-8'));jobs=[]
def visit(items,group=''):
 for i in items:
  if i.get('items'):visit(i['items'],i.get('name',i.get('title','')))
  elif i.get('type')=='gjirafa_episode':jobs.append((i,group))
visit(next(s for s in cfg['sections']if s['id']=='filma-shqip')['items']);out=P/'gjirafa-playback-verified';out.mkdir(exist_ok=True)
headers={'Referer':'https://video.gjirafa.com/','Origin':'https://video.gjirafa.com','User-Agent':'Mozilla/5.0'}
def run(job):
 i,group=job;handle=i['pageUrl'].rstrip('/').split('/')[-1];e=metadata.get(handle);r={'id':i['id'],'pageUrl':i['pageUrl'],'group':group,'title':i.get('videoTitle'),'checkedAt':'2026-11-15'}
 existing=out/(i['id']+'.json')
 if existing.exists():
  saved=json.loads(existing.read_text(encoding='utf-8'))
  if saved.get('status')=='hls_verified' and saved.get('pageUrl')==i['pageUrl']:return saved['status']
 try:
  if not e:e={'videoExternalId':None}
  r['externalId']=e['videoExternalId'];res=requests.get('https://vp-api.gjirafa.tech/api/videos/'+e['videoExternalId']+'/secure-link',headers=headers,timeout=15) if e['videoExternalId'] else None
  if res is not None and res.ok and res.json().get('success'):url=res.json()['result'];r['method']='official_secure_link'
  else:
   page=requests.get(i['pageUrl'],headers=headers,timeout=15);page.raise_for_status();parts=[]
   for m in re.finditer(r'self\.__next_f\.push\(',page.text):
    try:
     a=json.JSONDecoder().raw_decode(page.text[m.end():])[0]
     if len(a)>1 and isinstance(a[1],str):parts.append(a[1])
    except Exception:pass
   flight=''.join(parts)
   def find(o):
    if isinstance(o,dict):
     if o.get('handle')==handle and 'playerConfig'in o:return o
     for v in o.values():
      result=find(v)
      if result:return result
    if isinstance(o,list):
     for v in o:
      result=find(v)
      if result:return result
   video=None
   for m in re.finditer(r'(?:^|\n|\})[0-9a-f]+:(?=[\[{])',flight):
    try:root=json.JSONDecoder().raw_decode(flight[m.end():])[0]
    except Exception:continue
    video=find(root)
    if video:break
   assert video and not video.get('playerConfig',{}).get('hasDRM')
   urls=video['playerConfig'].get('playbackUrls',[])+video['playerConfig'].get('dvrPlaybackUrls',[])
   url=next(u['file']for u in urls if '.m3u8'in u.get('file',''));r['method']='official_page_public_hls'
   endpoint=(video.get('geoBlockConfig')or{}).get('secureLink')
   if endpoint:
    auth=requests.get(endpoint,headers=headers,timeout=15);auth.raise_for_status();data=auth.json();assert data['success'];url=data['result'];r['method']='official_page_secure_link'
   r['externalId']=video.get('playerConfig',{}).get('videoExternalId')
  res=requests.get(url,headers=headers,timeout=15);r['masterHttp']=res.status_code;res.raise_for_status();assert res.text.startswith('#EXTM3U')
  variant=next(l for l in res.text.splitlines()if l and not l.startswith('#'));vurl=urljoin(url,variant);res=requests.get(vurl,headers=headers,timeout=15);r['variantHttp']=res.status_code;res.raise_for_status();assert res.text.startswith('#EXTM3U');r['status']='hls_verified'
 except Exception as exc:r['status']='failed';r['error']=type(exc).__name__+': '+str(exc).split(' for url:')[0][:150]
 (out/(i['id']+'.json')).write_text(json.dumps(r,ensure_ascii=False,indent=2),encoding='utf-8')
 return r['status']
print('Checking',len(jobs),'Gjirafa manifests and variants',flush=True)
from collections import Counter
with concurrent.futures.ThreadPoolExecutor(max_workers=3)as pool:print(dict(Counter(pool.map(run,jobs))),flush=True)
