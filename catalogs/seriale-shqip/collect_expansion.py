import requests,json,re,concurrent.futures,yt_dlp
from pathlib import Path
p=Path('series-catalog/expansion')
jobs=[('shpija','https://www.youtube.com/@promedia-official/videos'),('shpresa','https://www.youtube.com/@kuroratv/videos'),('gruaja','https://www.youtube.com/channel/UCDdQzhTnTvgy32_3ruRbdkA/videos'),('kojshillak','https://www.youtube.com/channel/UCHcJXpfCU3J6qzWUJBODBTw/videos'),('osm','https://www.youtube.com/channel/UCWcHXbvZ26jPFryzw7EwCiA/videos'),('fara','https://www.youtube.com/channel/UCRhvqaDf4CEDAzrRvYe8wfQ/videos'),('stupcat','https://www.youtube.com/channel/UC1FXE1atv7BSDTlLRG_LtjA/videos'),('rtk','https://www.youtube.com/channel/UCLKm461v_m6OcgJOQDlXuuw/search?query=shpija'),('rtsh','https://www.youtube.com/watch?v=sb3DgwLgc4U')]
jobs=[('digitalb-osm','https://www.youtube.com/channel/UChy3ujfVZ7qoOXQA-h_Nuog/search?query=O%20sa%20mire')]
def run(j):
 name,url=j
 try:
  with yt_dlp.YoutubeDL({'quiet':True,'no_warnings':True,'extract_flat':True,'skip_download':True,'socket_timeout':15,'retries':0})as y:d=y.extract_info(url,download=False)
  fields=['id','title','duration','channel','channel_id','description','timestamp','release_timestamp','live_status','webpage_url']
  out={k:d.get(k)for k in fields};out['entries']=[{k:e.get(k)for k in fields}for e in d.get('entries',[])if e]
  (p/(name+'.json')).write_text(json.dumps(out,ensure_ascii=False,indent=2),encoding='utf-8');print(name,out['channel_id'],len(out['entries']),flush=True)
 except Exception as e:print(name,str(e),flush=True)
with concurrent.futures.ThreadPoolExecutor(max_workers=3)as pool:list(pool.map(run,jobs))
