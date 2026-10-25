import json
import os
import re
import urllib.request
import html

CONFIG_FILE = "config.json"
CINEMA_SECTION_ID = "cinema"
SOURCE_URL = "https://streamingcommunityz.build/"

def get_html(url):
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36'}
    req = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            return resp.read().decode('utf-8', errors='ignore')
    except Exception as e:
        print(f"Error fetching {url}: {e}")
        return ""

def main():
    print("Scaricando i film in tendenza da StreamingCommunity...")
    raw = get_html(SOURCE_URL)
    m = re.search(r'data-page=["\']([^"\']+)["\']', raw)
    
    if not m:
        print("Impossibile trovare i dati Inertia.js sulla pagina principale.")
        return

    data = json.loads(html.unescape(m.group(1)))
    props = data.get('props', {})
    sliders = props.get('sliders', [])
    
    items = []
    seen_ids = set()
    
    for slider in sliders:
        titles = slider.get('titles', [])
        for t in titles:
            tid = t.get('id')
            if tid and tid not in seen_ids:
                seen_ids.add(tid)
                name = t.get('name')
                slug = t.get('slug')
                ttype = t.get('type')
                
                images = t.get('images', [])
                poster_file = next((i.get('filename') for i in images if i.get('type') == 'poster'), None)
                poster_url = f"https://cdn.vixcloud.co/images/{poster_file}" if poster_file else ""
                page_url = f"https://streamingcommunityz.build/titles/{tid}-{slug}"
                
                items.append({
                    "id": f"sc-{tid}",
                    "name": name,
                    "subtitle": ttype.upper() if ttype else "FILM",
                    "icon": poster_url,
                    "type": "dynamic_hls",
                    "pageUrl": page_url,
                    "forceWeb": True,
                    "externalBrowser": True
                })

    print(f"Trovati {len(items)} film/serie in tendenza.")
    if not items:
        return

    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            config_data = json.load(f)
            
        cinema_section = next((s for s in config_data.get('sections', []) if s.get('id') == CINEMA_SECTION_ID), None)
        if cinema_section:
            cinema_section['items'] = items
            cinema_section['subtitle'] = f"Film e Serie in tendenza ({len(items)})"
            with open(CONFIG_FILE, "w", encoding="utf-8") as f:
                json.dump(config_data, f, indent=2, ensure_ascii=False)
            print("config.json aggiornato con successo!")

if __name__ == '__main__':
    main()
