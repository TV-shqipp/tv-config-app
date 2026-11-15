import requests,json,re,concurrent.futures,unicodedata
from pathlib import Path
P=Path('film-discovery/oha-live');P.mkdir(exist_ok=True)
names=['Film Aksion','Film Komedi','Film Thriller','Film Hits','Tring Action','Tring Comedy','Tring Fantasy','Tring Classic','Tring Shqip']
def key(n):return re.sub('[^a-z0-9]','',re.sub(r'\b(fhd|hd|sd)\b','',re.sub(r'\s*\(\d+\)\s*$','',n.lower())))
def run(name):
 out={'name':name,'variants':[],'checkedAt':'2026-11-15'}
 try:
  r=requests.get('https://oha.to/live/catalog/live/channels.json',params={'search':name},timeout=15);r.raise_for_status();es=r.json().get('items',[])
  for e in es:
   if key(e['name'])!=key(name):continue
   row={'id':e['id'],'name':e['name'],'pageUrl':e['url']};out['variants'].append(row)
   try:
    r=requests.get('https://oha.to/live/resolve',params={'url':e['url']},timeout=15);row['resolveHttp']=r.status_code;r.raise_for_status();d=r.json();url=d.get('url')
    if not url:row['error']='No public stream URL';continue
    with requests.get(url,headers={'User-Agent':'Mozilla/5.0'},timeout=15,stream=True)as res:row['manifestHttp']=res.status_code;row['hls']=res.status_code==200 and res.raw.read(7)==b'#EXTM3U'
   except Exception as exc:row['error']=type(exc).__name__
  out['available']=any(v.get('hls')for v in out['variants'])
 except Exception as exc:out['error']=type(exc).__name__
 (P/(key(name)+'.json')).write_text(json.dumps(out,ensure_ascii=False,indent=2),encoding='utf-8');print(name,out.get('available'),len(out['variants']),flush=True)
 return out
with concurrent.futures.ThreadPoolExecutor(max_workers=3)as pool:results=list(pool.map(run,names))
items=[]
for row in results:
 if not row.get('available'):continue
 name=row['name'];e=next(v for v in row['variants']if v.get('hls'))
 items.append(dict(id='oha-'+key(name),name=name,type='oha_live',subtitle='Drejtpërdrejt',pageUrl=e['pageUrl'],state='live'))
group=dict(id='filma-live',name='Filma Live',type='group',subtitle='Kanale filmash',items=items)
(P/'app-group.json').write_text(json.dumps(group,ensure_ascii=False,indent=2),encoding='utf-8')
for path in [Path('app/src/main/assets/config.json'),Path('film-discovery/remote/config.json')]:
 cfg=json.loads(path.read_text(encoding='utf-8'));sec=next(s for s in cfg['sections']if s['id']=='tv');sec['items']=[i for i in sec['items']if i['id']!='filma-live']+[group];cfg['version']+=1;path.write_text(json.dumps(cfg,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
