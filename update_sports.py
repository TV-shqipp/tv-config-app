import json
import re
import sys
import urllib.parse
import requests
from bs4 import BeautifulSoup

CONFIG_FILE = "config.json"
SPORT_SECTION_ID = "sport"
SOURCE_URL = "https://kosovari.online/"

def load_config():
    with open(CONFIG_FILE, "r", encoding="utf-8") as f:
        return json.load(f)

def save_config(data):
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

def extract_real_stream_link(page_url, headers):
    """Entra nella pagina di Google Sites e cerca l'iframe del player."""
    try:
        print(f"   -> Analisi pagina: {page_url}")
        resp = requests.get(page_url, headers=headers, timeout=10)
        soup = BeautifulSoup(resp.text, "html.parser")
        
        iframes = soup.find_all("iframe")
        
        # Domini pubblicitari da ignorare
        ad_domains = ["googlesyndication", "doubleclick", "googleadservices"]
        
        for iframe in iframes:
            src = iframe.get("src")
            if not src:
                continue
            if any(ad in src for ad in ad_domains):
                continue
                
            # Rende il link assoluto (a volte Google Sites usa link relativi)
            src = urllib.parse.urljoin(page_url, src)
            
            # Controlla che tipo di player è
            if "youtube.com" in src or "youtu.be" in src or "youtube-nocookie.com" in src:
                print(f"      -> Trovato YouTube: {src}")
                return "youtube", src
            elif ".m3u8" in src:
                print(f"      -> Trovato m3u8 diretto: {src}")
                return "hls", src
            elif "drive.google.com" in src:
                print(f"      -> Trovato Google Drive: {src}")
                return "hls", src
            elif "http" in src:
                print(f"      -> Trovato Player generico: {src}")
                return "dynamic_hls", src
                
    except Exception as e:
        print(f"      -> Errore estrazione: {e}")
        
    print("      -> Nessun player trovato, uso la pagina originale.")
    return "dynamic_hls", page_url

def fetch_matches():
    print(f"-> Connessione a {SOURCE_URL} ...")
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    }
    try:
        resp = requests.get(SOURCE_URL, headers=headers, timeout=15)
        resp.raise_for_status()
    except Exception as e:
        print(f"ERRORE DI RETE: {e}")
        return []
    
    print("-> Pagina scaricata, inizio l'analisi HTML...")
    soup = BeautifulSoup(resp.text, "html.parser")
    matches = []
    
    match_divs = soup.find_all("div", class_="AF_Match")
    print(f"-> Trovati {len(match_divs)} blocchi partita. Inizio analisi approfondita...")
    
    for match_div in match_divs:
        try:
            teams = match_div.find_all("div", class_="AF_TeamName")
            if len(teams) < 2:
                continue
            team1 = teams[0].get_text(strip=True)
            team2 = teams[1].get_text(strip=True)
            match_name = f"{team1} - {team2}"
            
            link_tag = match_div.find("a", class_="AF_EventMask")
            if not link_tag or not link_tag.get("href"):
                continue
            link = urllib.parse.urljoin(SOURCE_URL, link_tag["href"])
            
            icon_tag = match_div.find("div", class_="AF_TeamLogo").find("img") if match_div.find("div", class_="AF_TeamLogo") else None
            icon = icon_tag["src"] if icon_tag and icon_tag.get("src") else ""
            icon = urllib.parse.urljoin(SOURCE_URL, icon)
            
            # Esegue l'analisi profonda per trovare il player
            real_type, real_url = extract_real_stream_link(link, headers)
            
            match_id = "match-" + re.sub(r'[^a-z0-9]', '-', match_name.lower())
            
            match_item = {
                "id": match_id,
                "name": match_name,
                "icon": icon,
                "subtitle": "Partita di calcio"
            }
            
            # Assegna i campi corretti in base al tipo trovato
            if real_type == "dynamic_hls":
                match_item["type"] = "dynamic_hls"
                match_item["pageUrl"] = real_url
            else:
                match_item["type"] = real_type
                match_item["url"] = real_url
                
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
        
    existing_fixed = [item for item in sport_section.get("items", []) if not item.get("id", "").startswith("match-")]
    sport_section["items"] = existing_fixed + new_matches
    
    save_config(data)
    print(f"config.json aggiornato con {len(new_matches)} partite.")

if __name__ == "__main__":
    main()
