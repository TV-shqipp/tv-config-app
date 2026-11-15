import requests,json,re,concurrent.futures
from pathlib import Path
p=Path('series-catalog/expansion');jobs=[]
for name,key in [('shpija','shpija e nuses'),('gruaja','gruaja'),('shpresa','shpres'),('kojshillak','kojshillak')]:
 d=json.loads((p/(name+'.json')).read_text(encoding='utf-8'));es=[e for e in d['entries']if key in e['title'].lower() and (e.get('duration')or 0)>900 and 'promo' not in e['title'].lower()][:4]
 jobs.extend((name,e['id'])for e in es)
def run(j):
 name,id=j
 try:
  h=requests.get('https://www.youtube.com/watch?v='+id+'&hl=en',headers={'User-Agent':'Mozilla/5.0','Cookie':'SOCS=CAI'},timeout=15);h.raise_for_status();m=re.search(r'(?:var\s+)?ytInitialPlayerResponse\s*=\s*',h.text);d=json.JSONDecoder().raw_decode(h.text[m.end():])[0]
  v=d.get('videoDetails',{});micro=d.get('microformat',{}).get('playerMicroformatRenderer',{});r=dict(series=name,id=id,details=v,microformat=micro,status=d.get('playabilityStatus'));(p/('watch-'+id+'.json')).write_text(json.dumps(r,ensure_ascii=False,indent=2),encoding='utf-8');print(name,id,micro.get('publishDate'),micro.get('liveBroadcastDetails'),flush=True)
 except Exception as e:print(name,id,str(e),flush=True)
with concurrent.futures.ThreadPoolExecutor(max_workers=3)as pool:list(pool.map(run,jobs))
