import json
import re
import sys
import urllib.parse
import urllib.request
import os

CONFIG_FILE = "config.json"
SPORT_SECTION_ID = "sport"
SOURCE_URL = "https://kosovari.online/"

def load_config():
    with open(CONFIG_FILE, "r", encoding="utf-8") as f:
        return json.load(f)

def save_config(data):
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

def get_html(url, referer=None):
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36'
    }
    if referer:
        headers['Referer'] = referer
    req = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            return resp.read().decode('utf-8', errors='ignore')
    except Exception as e:
        print(f"      -> Errore lettura {url}: {e}")
        return ""

def extract_real_stream_link(google_sites_url):
    """
    Segue la catena di redirect:
    1) Google Sites -> estrae link 'www.google.com/url?q=...'
    2) Blogger (fitnessshapesstyle.net) -> estrae iframe dell'AlbaPlayer (healthfirstin.com)
    """
    try:
        print(f"   -> Analisi Google Sites: {google_sites_url}")
        html_google = get_html(google_sites_url)
        
        # 1. Trova il link di reindirizzamento Google per il blog
        match_google = re.search(r'https://www\.google\.com/url\?q=([^&"]+)', html_google)
        if not match_google:
            print("      -> Nessun link di reindirizzamento trovato in Google Sites.")
            return google_sites_url

        blogger_url = urllib.parse.unquote(match_google.group(1))
        print(f"      -> Trovato Blog: {blogger_url}")

        # 2. Scarica il blog e cerca l'iframe del player
        html_blogger = get_html(blogger_url, referer=google_sites_url)
        match_alba = re.search(r'<iframe.*?src=["\']([^"\']*albaplayer[^"\']*)["\']', html_blogger)
        if not match_alba:
            match_alba = re.search(r'<iframe.*?src=["\']([^"\']+)["\']', html_blogger)
            
        if match_alba:
            player_url = match_alba.group(1)
            if player_url.startswith('//'):
                player_url = 'https:' + player_url
            print(f"      -> Trovato AlbaPlayer finale: {player_url}")
            return player_url

        print("      -> Iframe non ancora attivo (partita non iniziata). Uso il Blog.")
        return blogger_url

    except Exception as e:
        print(f"      -> Errore analisi profonda: {e}")
        return google_sites_url

def fetch_matches():
    print(f"-> Connessione a {SOURCE_URL} ...")
    html_home = get_html(SOURCE_URL)
    if not html_home:
        print("ERRORE DI RETE: Impossibile scaricare la pagina principale.")
        return []

    print("-> Pagina scaricata, inizio l'analisi dei blocchi partita...")
    
    # Estrae tutti i blocchi partita
    blocks = re.findall(r'<div[^>]*class=["\'][^"\']*AF_Match[^"\']*["\'][^>]*>(.*?)</a>\s*</div>', html_home, re.DOTALL)
    print(f"-> Trovati {len(blocks)} blocchi partita. Inizio analisi approfondita...")

    matches = []
    seen_ids = set()

    for b in blocks:
        try:
            link_m = re.search(r'href=["\'](https://sites\.google\.com/[^"\']+)["\']', b)
            if not link_m:
                continue
            google_link = link_m.group(1)

            # Estrae il nome dal link slug
            slug = google_link.split('/')[-1].replace('-', ' ').title()
            match_name = slug

            match_id = "match-" + re.sub(r'[^a-z0-9]', '-', match_name.lower())
            if match_id in seen_ids:
                continue
            seen_ids.add(match_id)

            print(f"\n[Partita] {match_name}")
            real_url = extract_real_stream_link(google_link)

            match_item = {
                "id": match_id,
                "name": match_name,
                "icon": "https://kosovari.online/wp-content/uploads/2026/03/grok_image_tbtqj7-removebg-preview-1.png",
                "subtitle": "Partita di Calcio",
                "type": "dynamic_hls",
                "pageUrl": real_url,
                "referer": "https://kosovari.online/",
                "forceWeb": True
            }

            matches.append(match_item)

        except Exception as e:
            print(f"Errore parsing singola partita: {e}")

    return matches

def main():
    print(f"Inizio aggiornamento sport...")
    new_matches = fetch_matches()

    if not new_matches:
        print("Nessuna partita trovata. Il file config.json non verrà modificato.")
        sys.exit(0)

    data = load_config()
    sport_section = None
    for section in data.get("sections", []):
        if section.get("id") == SPORT_SECTION_ID:
            sport_section = section
            break

    if sport_section is None:
        print("Sezione 'sport' non trovata nel config.json.")
        sys.exit(1)

    sport_section["items"] = new_matches
    sport_section["subtitle"] = f"Partite di oggi ({len(new_matches)})"

    save_config(data)
    print(f"\nconfig.json aggiornato con successo con {len(new_matches)} partite!")

    path = os.environ.get("GITHUB_OUTPUT")
    if path:
        with open(path, "a", encoding="utf-8") as f:
            f.write("run=true\n")

if __name__ == "__main__":
    main()
