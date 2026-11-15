import json,re,unicodedata,collections
from pathlib import Path
P=Path(__file__).parent;R=P/'expansion'
def read(p):return json.loads(p.read_text(encoding='utf-8-sig'))
def norm(t):return ''.join(c for c in unicodedata.normalize('NFKD',t or '')if not unicodedata.combining(c)).lower()
def number(t):
 m=re.search(r'\b(?:episod[iae]?|ep)\s*[.:-]?\s*(\d+)',norm(t))
 return int(m[1]) if m else None
def season(t):
 m=re.search(r'sezon[ia]\s*(?:i\s+)?([0-9]+|[ivx]+)',norm(t))
 if not m:return 'Epizodat'
 v=m[1];roman={'i':1,'ii':2,'iii':3,'iv':4,'v':5,'vi':6,'vii':7,'viii':8,'ix':9,'x':10}
 return 'Sezoni '+str(roman.get(v,v))
exclude=r'\b(promo|trailer|teaser|clip|klip|short|pjese|prapasken\w*|best of|dokumentari)\b'
specs=[('o-sa-mire','O sa mirë','osm','o sa mire'),('cka-ka-shpija','Çka ka shpija','rtk','cka ka shpija'),('egjeli','Egjeli',None,'egjeli'),('schengen-visa','Schengen Visa',None,'schengen visa'),('rrushe','Rrushe',None,'rrushe'),('njerez-dhe-fate','Njerëz dhe fate','rtsh-episodes','njerez dhe fate'),('fara-e-flliqt','Fara e flliqt','fara','fara e flliqt')]
add=[];audits=[]
for sid,name,source,key in specs:
 groups=collections.defaultdict(lambda:collections.defaultdict(list));rejected=[]
 def accept(e,g,n,platform,channel,official=True):
  t=e.get('title',e.get('name',''));dur=e.get('duration')or 0
  if not n or dur<900 or re.search(exclude,norm(t)):
   rejected.append({'title':t,'reason':'number, duration or excluded content','id':e.get('id',e.get('contentId'))});return
  checked=False
  if platform=='youtube':
   meta_path=R/'verified'/(e['id']+'.json')
   if meta_path.exists():
    meta=read(meta_path)
    if meta.get('status') not in (None,'OK'):
     rejected.append(dict(title=t,id=e['id'],reason='Watch page: '+meta['status']));return
    if meta.get('status')=='OK':
     if meta.get('channelId')!=channel or number(meta.get('title',''))!=n or int(meta.get('lengthSeconds')or 0)<900:
      rejected.append(dict(title=t,id=e['id'],reason='Watch metadata mismatch'));return
     t=meta['title'];dur=int(meta['lengthSeconds']);checked=True
  url='https://www.youtube.com/watch?v='+e['id'] if platform=='youtube' else 'https://video.gjirafa.com/'+e['handle']
  groups[g][n].append(dict(title=t,duration=dur,url=url,id=e.get('id',e.get('contentId')),platform=platform,channel=channel,official=official,verification='watch_metadata_checked' if checked else 'public_listing',thumbnail=e.get('thumbnail')))
 if source:
  source_names=[source]+({'o-sa-mire':['osm-playlist','digitalb-osm'],'cka-ka-shpija':['klankosova-shpija']}.get(sid,[]))
  inventories=[read(R/(src+'.json')) for src in source_names if (R/(src+'.json')).exists()]
  for e in [dict(e,channel_id=e.get('channel_id') or d.get('channel_id')) for d in inventories for e in d['entries']]:
   t=norm(e['title'])
   if key not in t and not (sid=='fara-e-flliqt' and 'fare e flliqt' in t):continue
   g='Reality' if sid=='o-sa-mire' and 'reality' in t else season(t)
   n=number(t)
   if sid=='fara-e-flliqt' and g=='Epizodat' and n and n<=15:
    g='Epizodat 1–15'
   accept(e,g,n,'youtube',e.get('channel_id'))
 slug={'egjeli':'egjeli','rrushe':'rrushe','schengen-visa':'schengenvisa'}.get(sid)
 if slug:
  for f in R.glob(slug+'-season-*.json'):
   d=read(f);g=d['season']['name']
   for e in d['items']:
    n=number(e['name'])
    if sid=='schengen-visa':
     m=re.search(r'schengen visa\s*[-:]\s*(\d+)\.',norm(e['name']));n=int(m[1])if m else n
    accept(e,g,n,'gjirafa','Gjirafa Studios')
 if sid=='egjeli':
  d=read(R/'stupcat.json')
  for e in d['entries']:
   t=norm(e['title'])
   if 'egjeli' not in t:continue
   n=number(t)
   if not n:continue
   if 'sezoni' in t:g=season(t)
   elif '2016' in t:g='Egjeli 2016'
   elif '(hd)' in t:g='Egjeli HD'
   else:g='Egjeli 2016'
   accept(e,g,n,'youtube',d['channel_id'])
 children=[];rows=[];missing={}
 # Keep documented seasons in numeric order; do not invent seasons for cumulative uploads.
 def group_key(pair):
  g,es=pair
  if sid=='fara-e-flliqt' and g.startswith('Epizodat 1'):return (0,0)
  if g=='Epizodat' and sid!='fara-e-flliqt':return (0,0)
  if sid=='egjeli' and g in ('Egjeli HD','Egjeli 2016','Egjeli - Epizodat tjera'):
   return (0,{'Egjeli HD':0,'Egjeli - Epizodat tjera':1,'Egjeli 2016':2}[g])
  m=re.match(r'Sezoni (\d+)$',g)
  if m:return (1,int(m[1]))
  if g=='Reality':return (3,0)
  return (2,min(es) if es else 0)
 for gi,(g,episodes)in enumerate(sorted(groups.items(),key=group_key)):
  if g=='Epizodat':display_group=f'Epizodat {min(episodes)}–{max(episodes)}'
  else:display_group=g
  items=[]
  for n,alternatives in sorted(episodes.items()):
   alternatives.sort(key=lambda e: (e['platform']!='youtube',e['verification']!='watch_metadata_checked'))
   e=alternatives[0];it=dict(id=f'{sid}-g{gi}-e{n}',name=f'Episodi {n}',episodeNumber=n,videoTitle=e['title'],state='vod',subtitle=f"{e['channel']} · {round(e['duration']/60)} min",pageUrl=e['url'])
   if e['platform']=='youtube':it.update(type='hls',url='',videoId=e['id'],icon=f"https://i.ytimg.com/vi/{e['id']}/hqdefault.jpg")
   else:it.update(type='gjirafa_episode',icon=e['thumbnail'])
   items.append(it);rows.append(dict(group=g,episode=n,sources=alternatives))
  missing[g]=[n for n in range(min(episodes),max(episodes)+1)if n not in episodes] if episodes else []
  children.append(dict(id=f'{sid}-g{gi}',name=display_group,type='group',subtitle=f'{len(items)} episode',items=items))
 if source:
  specials=[];seen=set()
  for inventory in inventories:
   for e in inventory['entries']:
    t=norm(e.get('title'))
    if key not in t or number(t) or not re.search('festiv|special',t) or (e.get('duration')or 0)<900 or t in seen:continue
    seen.add(t);url='https://www.youtube.com/watch?v='+e['id']
    specials.append(dict(id=sid+'-special-'+e['id'],name=e['title'],videoTitle=e['title'],type='hls',url='',videoId=e['id'],pageUrl=url,state='vod',icon='https://i.ytimg.com/vi/'+e['id']+'/hqdefault.jpg'))
    rows.append(dict(group='Speciale',episode=None,sources=[dict(id=e['id'],title=e['title'],platform='youtube',url=url,official=True,channel=inventory.get('channel_id'),verification='public_listing')]))
  if specials:children.append(dict(id=sid+'-speciale',name='Speciale',type='group',subtitle=str(len(specials))+' episode',items=specials))
 card=dict(id=sid,name=name,type='group',subtitle='Krejt epizodat',items=children)
 if children:card['icon']=children[0]['items'][0].get('icon')
 (R/(sid+'.app-section.json')).write_text(json.dumps(card,ensure_ascii=False,indent=2),encoding='utf-8')
 add.append(card);audit=dict(id=sid,title=name,complete=False,checkedAt='2026-11-15',rows=rows,rejected=rejected,missingWithinObservedNumbering=missing,note='Missing numbers are search targets, not proof that episodes existed. Listing metadata checked; watch playback not exhaustively verified. Official source inventories only; global search alternatives retained in expansion/*.json.')
 (R/(sid+'.audit.json')).write_text(json.dumps(audit,ensure_ascii=False,indent=2),encoding='utf-8');audits.append((name,len(rows),missing))
latest=[('shpija-e-nuses','Shpija e Nuses','shpija'),('gruaja','Gruaja','gruaja'),('ne-kerkim-te-shpreses','Në kërkim të Shpresës','shpresa'),('kojshillak','Kojshillak','kojshillak')]
for sid,name,source in latest:
 es=[e for e in read(R/(source+'.json'))['entries'] if norm(name)in norm(e['title']) and number(e['title']) and (e.get('duration')or 0)>=900 and not re.search(exclude,norm(e['title']))];e=max(es,key=lambda e:number(e['title']))
 add.insert(0,dict(id=sid,name=name,subtitle='Epizodi i fundit',type='hls',url='',videoId=e['id'],videoTitle=e['title'],state='vod',icon=f"https://i.ytimg.com/vi/{e['id']}/hqdefault.jpg"))
for path in [P.parent/'app/src/main/assets/config.json',P.parent/'film-discovery/remote/config.json']:
 cfg=read(path);sec=next(s for s in cfg['sections']if s['id']=='filma-shqip');ids={e['id']for e in add};sec['items']=[e for e in sec['items']if e['id']not in ids]+add;sec['title']='Seriale Shqip';cfg['version']=max(cfg.get('version',0)+1,2026111501);path.write_text(json.dumps(cfg,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print([(n,c)for n,c,m in audits])
