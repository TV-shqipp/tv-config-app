import json
import re
import sys
import requests
from bs4 import BeautifulSoup
from datetime import datetime

CONFIG_FILE = "config.json"
SPORT_SECTION_ID = "sport"
SOURCE_URL = "https://kosovari.online/"

def load_config():
    with open(CONFIG_FILE, "r", encoding="utf-8") as f:
        return json.load(f)

def save_config(data):
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

def fetch_matches():
    """Scarica la pagina e restituisce una lista di partite (nome, link, icona)."""
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    }
    resp = requests.get(SOURCE_URL, headers=headers, timeout=15)
    resp.raise_for_status()
    
    soup = BeautifulSoup(resp.text, "html.parser")
    matches = []
    
    # Trova tutti i blocchi delle partite
    for match_div in soup.find_all("div", class_="AF_Match"):
        try:
            # Estrai i nomi delle squadre
            teams = match_div.find_all("div", class_="AF_TeamName")
            if len(teams) < 2:
                continue
            team1 = teams[0].get_text(strip=True)
            team2 = teams[1].get_text(strip=True)
            match_name = f"{team1} - {team2}"
            
            # Estrai il link (l'elemento <a> con classe AF_EventMask)
            link_tag = match_div.find("a", class_="AF_EventMask")
            if not link_tag or not link_tag.get("href"):
                continue
            link = link_tag["href"]
            
            # Estrai l'icona della prima squadra (opzionale)
            icon_tag = match_div.find("div", class_="AF_TeamLogo").find("img") if match_div.find("div", class_="AF_TeamLogo") else None
            icon = icon_tag["src"] if icon_tag and icon_tag.get("src") else ""
            
            # Genera un ID univoco e pulito
            match_id = "match-" + re.sub(r'[^a-z0-9]', '-', match_name.lower())
            
            matches.append({
                "id": match_id,
                "name": match_name,
                "icon": icon,
                "type": "dynamic_hls",
                "pageUrl": link,
                "subtitle": "Partita di calcio"
            })
        except Exception as e:
            print(f"Errore parsing partita: {e}")
            continue
            
    return matches

def main():
    print(f"Inizio aggiornamento sport da {SOURCE_URL}...")
    try:
        new_matches = fetch_matches()
    except Exception as e:
        print(f"Errore durante il download: {e}")
        sys.exit(1)
        
    print(f"Trovate {len(new_matches)} partite.")
    
    data = load_config()
    sport_section = None
    for section in data.get("sections", []):
        if section.get("id") == SPORT_SECTION_ID:
            sport_section = section
            break
            
    if sport_section is None:
        print("Sezione 'sport' non trovata nel config.json.")
        sys.exit(1)
        
    # Mantieni gli elementi esistenti che NON sono partite (es. canali fissi)
    # I nostri elementi dinamici hanno l'ID che inizia con "match-"
    existing_fixed = [item for item in sport_section.get("items", []) if not item.get("id", "").startswith("match-")]
    
    # Unisci i canali fissi con le nuove partite
    sport_section["items"] = existing_fixed + new_matches
    
    save_config(data)
    print("config.json aggiornato con le nuove partite.")

if __name__ == "__main__":
    main()
