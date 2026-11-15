import json,re,requests,concurrent.futures,threading
from pathlib import Path
p=Path('series-catalog/expansion');jobs={}
for f in p.glob('*.audit.json'):
 for row in json.loads(f.read_text(encoding='utf-8'))['rows']:
  e=row['sources'][0]
  if e['platform']=='youtube':jobs[e['id']]=e
out=p/'verified';out.mkdir(exist_ok=True);blocked=threading.Event()
def run(id):
 f=out/(id+'.json')
 if f.exists() or blocked.is_set():return
 try:
  r=requests.get('https://www.youtube.com/watch?v='+id+'&hl=en',headers={'User-Agent':'Mozilla/5.0','Cookie':'SOCS=CAI'},timeout=15);
  if r.status_code==429 or '/sorry/' in r.url:
   blocked.set();raise ValueError('YouTube HTTP 429; verification stopped')
  r.raise_for_status();m=re.search(r'(?:var\s+)?ytInitialPlayerResponse\s*=\s*',r.text)
  if not m:raise ValueError('Player metadata unavailable')
  d=json.JSONDecoder().raw_decode(r.text[m.end():])[0];v=d.get('videoDetails',{});result=dict(id=id,status=d.get('playabilityStatus',{}).get('status'),**{k:v.get(k)for k in ['title','channelId','author','lengthSeconds','isLive','isUpcoming']})
 except Exception as e:result=dict(id=id,error=str(e))
 f.write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
print('Checking',len(jobs),'watch pages',flush=True)
with concurrent.futures.ThreadPoolExecutor(max_workers=3)as pool:
 for i,_ in enumerate(pool.map(run,jobs),1):
  if i%100==0:print(i,flush=True)
