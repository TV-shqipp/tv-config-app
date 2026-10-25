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
        with urllib.request.urlopen(req, timeout=8) as resp:
            return resp.read().decode('utf-8', errors='ignore')
    except Exception:
        return ""

def extract_m3u8(url, referer=None):
    """Scava nella pagina per trovare il link m3u8, anche entrando negli iframe."""
    html = get_html(url, referer=referer)
    if not html:
        return None
    
    # 1. Cerca un m3u8 diretto nel testo della pagina
    matches = re.findall(r'(https?://[^\s"\'<>]+\.m3u8[^\s"\'<>]*)', html)
    if matches:
        return matches[0]
    
    # 2. Se non c'è, cerca gli iframe e scava dentro di essi
    iframe_matches = re.findall(r'<iframe[^>]+src=["\']([^"\']+)["\']', html)
    for iframe_url in iframe_matches:
        if iframe_url.startswith('//'): 
            iframe_url = 'https:' + iframe_url
        elif iframe_url.startswith('/'):
            parsed = urllib.parse.urlparse(url)
            iframe_url = f"{parsed.scheme}://{parsed.netloc}{iframe_url}"
            
        print(f"         -> Scavo nell'iframe: {iframe_url[:60]}...")
        # Chiamata ricorsiva per scavare nell'iframe
        m3u8 = extract_m3u8(iframe_url, referer=url)
        if m3u8:
            return m3u8
            
    return None

def find_best_working_server(base_alba_url):
    """Testa automaticamente i server da 1 a 8 per trovare quello attivo e scava per l'm3u8."""
    # Priorità: 5 (DaddyLive), 3 (SirTV), 1 (Taifood), 8, 4, 2, 7
    for serv in [5, 3, 1, 8, 4, 2, 7]:
        test_url = f"{base_alba_url}?serv={serv}"
        print(f"      -> Test Server {serv}...")
        
        m3u8_url = extract_m3u8(test_url)
        if m3u8_url:
            print(f"      -> TROVATO M3U8 SUL SERVER {serv}!")
            return test_url, m3u8_url
            
    return None, None

def resolve_player_url(google_sites_url):
    """Segue i reindirizzamenti da Google Sites fino al miglior server AlbaPlayer."""
    try:
        print(f"   -> Analisi Google Sites: {google_sites_url}")
        html_google = get_html(google_sites_url)
        
        match_google = re.search(r'https://www\.google\.com/url\?q=([^&"]+)', html_google)
        if not match_google:
            return None, None

        blogger_url = urllib.parse.unquote(match_google.group(1))

        html_blogger = get_html(blogger_url, referer=google_sites_url)
        match_alba = re.search(r'<iframe.*?src=["\']([^"\']*albaplayer[^"\']*)["\']', html_blogger)
        if not match_alba:
            match_alba = re.search(r'<iframe.*?src=["\']([^"\']+)["\']', html_blogger)
            
        if not match_alba:
            return None, None

        alba_url = match_alba.group(1)
        if alba_url.startswith('//'):
            alba_url = 'https:' + alba_url

        base_alba = alba_url.split('?')[0]
        return find_best_working_server(base_alba)

    except Exception as e:
        print(f"      -> Errore: {e}")
        return None, None

def parse_kosovari_matches():
    html = get_html('https://kosovari.online/')
    if not html:
        return []

    matches = []
    # Usa BeautifulSoup per un parsing più pulito se disponibile
    try:
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(html, "html.parser")
        for match_div in soup.find_all("div", class_="AF_Match"):
            link_tag = match_div.find("a", class_="AF_EventMask")
            if not link_tag or not link_tag.get("href"): continue
            
            link = link_tag.get("href")
            teams = match_div.find_all("div", class_="AF_TeamName")
            if len(teams) >= 2:
                title = f"{teams[0].get_text(strip=True)} - {teams[1].get_text(strip=True)}"
            else:
                title = link.split('/')[-1].replace('-', ' ').title()
                
            icon_tag = match_div.find("div", class_="AF_TeamLogo").find("img") if match_div.find("div", class_="AF_TeamLogo") else None
            icon = icon_tag["src"] if icon_tag and icon_tag.get("src") else "https://kosovari.online/wp-content/uploads/2026/03/grok_image_tbtqj7-removebg-preview-1.png"
            
            matches.append({"title": title, "link": link, "icon": icon})
    except Exception:
        # Fallback regex se bs4 fallisce
        blocks = re.findall(r'<div[^>]*class=["\'][^"\']*AF_Match[^"\']*["\'][^>]*>(.*?)</a>\s*</div>', html, re.DOTALL)
        for b in blocks:
            link_m = re.search(r'href=["\'](https://sites\.google\.com/[^"\']+)["\']', b)
            if link_m:
                link = link_m.group(1)
                slug = link.split('/')[-1].replace('-', ' ').title()
                matches.append({"title": slug, "link": link, "icon": ""})
        
    return matches

def main():
    print("Scaricando le partite da kosovari.online...")
    raw_matches = parse_kosovari_matches()
    print(f"Trovate {len(raw_matches)} partite su Kosovari Online.")
    
    new_items = []
    for m in raw_matches:
        title = m['title']
        print(f"Verifica e test server per {title}...")
        player_url, m3u8_url = resolve_player_url(m['link'])
        
        match_id = re.sub(r'[^a-zA-Z0-9-]', '', title.lower().replace(' ', '-'))
        
        if m3u8_url:
            # Abbiamo trovato il link diretto! Niente WebView, parte subito con ExoPlayer
            new_items.append({
                "id": f"sport-{match_id}",
                "name": title,
                "icon": m.get('icon', ""),
                "type": "hls",
                "url": m3u8_url,
                "referer": player_url or "https://kosovari.online/"
            })
            print(f"  -> OK (Link Diretto): {m3u8_url[:60]}...")
        elif player_url:
            # Fallback se non trova il file .m3u8 (magari è protetto da JS)
            new_items.append({
                "id": f"sport-{match_id}",
                "name": title,
                "icon": m.get('icon', ""),
                "type": "dynamic_hls",
                "pageUrl": player_url,
                "referer": "https://kosovari.online/",
                "forceWeb": True
            })
            print(f"  -> OK (WebView Fallback): {player_url}")
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
