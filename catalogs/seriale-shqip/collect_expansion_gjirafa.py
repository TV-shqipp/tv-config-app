import requests,re,json
from pathlib import Path
p=Path('series-catalog/expansion');headers={'User-Agent':'Mozilla/5.0','Origin':'https://video.gjirafa.com','Referer':'https://video.gjirafa.com/'}
for slug in ['rrushe','egjeli','schengen-visa','schengenvisa']:
 try:
  h=requests.get('https://video.gjirafa.com/'+slug,headers=headers,timeout=20);h.raise_for_status();parts=[]
  for m in re.finditer(r'self\.__next_f\.push\(',h.text):
   try:
    a=json.JSONDecoder().raw_decode(h.text[m.end():])[0]
    if len(a)>1 and isinstance(a[1],str):parts.append(a[1])
   except Exception:pass
  stream=''.join(parts);(p/(slug+'-page.txt')).write_text(stream,encoding='utf-8');m=re.search(r'"seasons":',stream)
  if not m:print(slug,'no seasons',flush=True);continue
  seasons=json.JSONDecoder().raw_decode(stream[m.end():])[0];(p/(slug+'-seasons.json')).write_text(json.dumps(seasons,ensure_ascii=False,indent=2),encoding='utf-8')
  for s in seasons:
   entries=[]
   for page in range(1,50):
    r=requests.get('https://edge.video.gjirafa.com/client/v1/contents/seasons/'+s['id']+'/episodes',params={'page':page,'pageSize':100},headers=headers,timeout=20);r.raise_for_status();d=r.json();es=d['items'];entries.extend(es)
    if len(entries)>=d.get('totalCount',len(entries)) or not es:break
   (p/(slug+'-season-'+s['id']+'.json')).write_text(json.dumps({'season':s,'items':entries},ensure_ascii=False,indent=2),encoding='utf-8');print(slug,s,len(entries),flush=True)
 except Exception as e:print(slug,str(e),flush=True)
