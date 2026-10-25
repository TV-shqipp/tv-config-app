import json
import urllib.request
import os
import sys

# In GitHub Actions useremo config.json
CONFIG_FILE = "config.json"

def load_config():
    with open(CONFIG_FILE, "r", encoding="utf-8") as f:
        return json.load(f)

def save_config(data):
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

def get_matches():
    req = urllib.request.Request('https://www.streamex.hn/api/live/matches/all', headers={'User-Agent': 'Mozilla/5.0'})
    resp = urllib.request.urlopen(req).read().decode('utf-8')
    return json.loads(resp)

def get_stream_embed(source_id, source_type):
    req = urllib.request.Request(f'https://www.streamex.hn/api/live/stream/{source_type}/{source_id}', headers={'User-Agent': 'Mozilla/5.0'})
    try:
        resp = urllib.request.urlopen(req).read().decode('utf-8')
        streams = json.loads(resp)
        if streams:
            # Cerca il flusso HD se disponibile, altrimenti prende il primo
            for s in streams:
                if s.get('hd') and s.get('embedUrl'):
                    return s['embedUrl']
            return streams[0].get('embedUrl')
    except Exception as e:
        print(f"Errore recupero stream per {source_id}: {e}")
    return None

def main():
    print("Scaricando le partite da streamex.hn...")
    matches = get_matches()
    
    new_items = []
    
    # L'API restituisce i match in diretta o previsti per oggi.
    for m in matches:
        title = m.get('title')
        match_id = m.get('id')
        poster = m.get('poster', '')
        if poster.startswith('/'):
            poster = 'https://www.streamex.hn' + poster
            
        sources = m.get('sources', [])
        embed_url = None
        if sources:
            # Prendiamo la prima sorgente (di solito admin o hotel)
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
    if sport_section:
        # Sostituisce l'intera sezione sport con le partite attuali
        sport_section['items'] = new_items
        sport_section['subtitle'] = f"Oggi ({len(new_items)} eventi)"
        save_config(data)
        print("config.json aggiornato con successo.")
        
        # Segnalazione per GitHub Actions
        path = os.environ.get("GITHUB_OUTPUT")
        if path:
            with open(path, "a", encoding="utf-8") as f:
                f.write(f"run=true\n")
    else:
        print("Sezione sport non trovata in config.json.")

if __name__ == '__main__':
    main()
