import json
import urllib.request
import os

CONFIG_FILE = "config.json"

def load_config():
    with open(CONFIG_FILE, "r", encoding="utf-8") as f:
        return json.load(f)

def save_config(data):
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

def get_headers():
    return {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36',
        'Accept': 'application/json, text/plain, */*',
        'Accept-Language': 'en-US,en;q=0.9',
        'Referer': 'https://www.streamex.hn/live'
    }

def get_matches():
    req = urllib.request.Request('https://www.streamex.hn/api/live/matches/all', headers=get_headers())
    try:
        resp = urllib.request.urlopen(req).read().decode('utf-8')
        return json.loads(resp)
    except Exception as e:
        print(f"Errore recupero lista partite: {e}")
        return []

def get_stream_embed(source_id, source_type):
    req = urllib.request.Request(f'https://www.streamex.hn/api/live/stream/{source_type}/{source_id}', headers=get_headers())
    try:
        resp = urllib.request.urlopen(req).read().decode('utf-8')
        streams = json.loads(resp)
        if streams:
            for s in streams:
                if s.get('hd') and s.get('embedUrl'):
                    return s['embedUrl']
            return streams[0].get('embedUrl')
    except Exception as e:
        pass
    return None

def main():
    print("Scaricando le partite da streamex.hn...")
    matches = get_matches()
    
    new_items = []
    
    for m in matches:
        title = m.get('title')
        match_id = m.get('id')
        poster = m.get('poster', '')
        if poster.startswith('/'):
            poster = 'https://www.streamex.hn' + poster
            
        sources = m.get('sources', [])
        embed_url = None
        if sources:
            src = sources[0]
            embed_url = get_stream_embed(src['id'], src['source'])
            
        if embed_url:
            new_items.append({
                "id": f"sport-{match_id}",
                "name": title,
                "icon": poster,
                "type": "dynamic_hls",
                "pageUrl": embed_url,
                "referer": "https://www.streamex.hn/"
            })
            print(f"Aggiunto: {title}")

    data = load_config()
    
    sport_section = next((s for s in data.get('sections', []) if s.get('id') == 'sport'), None)
    if sport_section and new_items:
        sport_section['items'] = new_items
        sport_section['subtitle'] = f"Oggi ({len(new_items)} eventi)"
        save_config(data)
        print("config.json aggiornato con successo.")
        
        path = os.environ.get("GITHUB_OUTPUT")
        if path:
            with open(path, "a", encoding="utf-8") as f:
                f.write("run=true\n")
    else:
        print("Nessuna nuova partita trovata o sezione sport mancante.")

if __name__ == '__main__':
    main()
