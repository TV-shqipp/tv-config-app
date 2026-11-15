import yt_dlp,json,concurrent.futures
from pathlib import Path
names=['Shpija e Nuses','Seriali Gruaja','Në kërkim të Shpresës','Kojshillak','O sa mirë','Çka ka shpija','Egjeli','Schengen Visa','Rrushe','Njerëz dhe fate','Fara e flliqt']
p=Path('series-catalog/expansion');p.mkdir(exist_ok=True)
def run(name):
 try:
  with yt_dlp.YoutubeDL({'quiet':True,'no_warnings':True,'extract_flat':True,'socket_timeout':15,'retries':0}) as y:d=y.extract_info('ytsearch40:'+name+' episodi',download=False)
  es=[{k:e.get(k) for k in ['id','title','duration','channel','channel_id','channel_url','url','live_status']} for e in d['entries'] if e]
  (p/(str(names.index(name))+'.json')).write_text(json.dumps(es,ensure_ascii=False,indent=2),encoding='utf-8')
  print(name,json.dumps(es[:4],ensure_ascii=True),flush=True)
 except Exception as e:print(name,str(e),flush=True)
with concurrent.futures.ThreadPoolExecutor(max_workers=3) as pool:list(pool.map(run,names))
