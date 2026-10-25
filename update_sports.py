import json
import os
import re
import sys
import urllib.parse
import urllib.request

CONFIG_FILE = "config.json"
SPORT_SECTION_ID = "sport"
SOURCE_URL = "https://kosovari.online/"

def get_html(url, referer=None):
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
    if referer:
        headers['Referer'] = referer
    req = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=5) as resp:
            return resp.read().decode('utf-8', errors='ignore')
    except Exception:
        return ""

def find_best_working_server(base_alba_url):
    """Testa automaticamente i server da 1 a 8 per trovare quello attivo (DaddyLive, SirTV, ecc.)."""
    # Priorità: 5 (DaddyLive), 3 (SirTV), 1 (Taifood), 8, 4, 2, 7
    for serv in [5, 3, 1, 8, 4, 2, 7]:
        test_url = f"{base_alba_url}?serv={serv}"
        html = get_html(test_url)
        if "thedaddy" in html or "sirtv" in html or "taifood" in html or "sources" in html:
            print(f"      -> Trovato Server attivo: {serv}")
            return test_url
    return None

def resolve_player_url(google_sites_url):
    """Segue i reindirizzamenti da Google Sites fino al miglior server AlbaPlayer."""
    try:
        print(f"   -> Analisi Google Sites: {google_sites_url}")
        html_google = get_html(google_sites_url)
        
        match_google = re.search(r'https://www\.google\.com/url\?q=([^&"]+)', html_google)
        if not match_google:
            return None

        blogger_url = urllib.parse.unquote(match_google.group(1))

        html_blogger = get_html(blogger_url, referer=google_sites_url)
        match_alba = re.search(r'<iframe.*?src=["\']([^"\']*albaplayer[^"\']*)["\']', html_blogger)
        if not match_alba:
            match_alba = re.search(r'<iframe.*?src=["\']([^"\']+)["\']', html_blogger)
            
        if not match_alba:
            return None

        alba_url = match_alba.group(1)
        if alba_url.startswith('//'):
            alba_url = 'https:' + alba_url

        base_alba = alba_url.split('?')[0]
        return find_best_working_server(base_alba)

    except Exception as e:
        print(f"      -> Errore: {e}")
        return None

def parse_kosovari_matches():
    html = get_html('https://kosovari.online/')
    if not html:
        return []

    matches = []
    blocks = re.findall(r'<div[^>]*class=["\'][^"\']*AF_Match[^"\']*["\'][^>]*>(.*?)</a>\s*</div>', html, re.DOTALL)
    
    for b in blocks:
        link_m = re.search(r'href=["\'](https://sites\.google\.com/[^"\']+)["\']', b)
        if not link_m:
            continue
        link = link_m.group(1)
        slug = link.split('/')[-1].replace('-', ' ').title()
        
        matches.append({
            "title": slug,
            "link": link
        })
        
    return matches

def main():
    print("Scaricando le partite da kosovari.online...")
    raw_matches = parse_kosovari_matches()
    print(f"Trovate {len(raw_matches)} partite su Kosovari Online.")
    
    new_items = []
    for m in raw_matches:
        title = m['title']
        print(f"Verifica e test server per {title}...")
        player_url = resolve_player_url(m['link'])
        
        if player_url:
            match_id = re.sub(r'[^a-zA-Z0-9-]', '', title.lower().replace(' ', '-'))
            new_items.append({
                "id": f"sport-{match_id}",
                "name": title,
                "icon": "https://kosovari.online/wp-content/uploads/2026/03/grok_image_tbtqj7-removebg-preview-1.png",
                "type": "dynamic_hls",
                "pageUrl": player_url,
                "referer": "https://kosovari.online/",
                "forceWeb": True
            })
            print(f"  -> OK: {player_url}")
        else:
            print("  -> Nessun server attivo al momento per questa partita.")

    if not new_items:
        print("Nessuna partita attiva trovata.")
        return

    with open(CONFIG_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)
        
    sport_section = next((s for s in data.get('sections', []) if s.get('id') == SPORT_SECTION_ID), None)
    if sport_section:
        sport_section['items'] = new_items
        sport_section['subtitle'] = f"Partite attive in diretta ({len(new_items)})"
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        print("config.json aggiornato con successo!")
        
        path = os.environ.get("GITHUB_OUTPUT")
        if path:
            with open(path, "a", encoding="utf-8") as f:
                f.write("run=true\n")

if __name__ == '__main__':
    main()
