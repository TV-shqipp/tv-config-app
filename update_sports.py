import json
import os
import re
import urllib.parse
import urllib.request

CONFIG_FILE = "config.json"
SPORT_SECTION_ID = "sport"
KOSOVARI_GROUP_ID = "sport-kosovari"
SOURCE_URL = "https://kosovari.online/"

def get_html(url, referer=None):
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
    if referer:
        headers['Referer'] = referer
    req = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            return resp.read().decode('utf-8', errors='ignore')
    except Exception:
        return ""

def find_best_working_server(base_alba_url):
    """Testa i server per trovare quello attivo. Se non ne trova, restituisce il server 1 di default."""
    for serv in [5, 3, 1, 8, 4, 2, 7]:
        test_url = f"{base_alba_url}?serv={serv}"
        html = get_html(test_url)
        # Check molto più permissivi per non scartare partite funzionanti
        if html and ("thedaddy" in html or "sirtv" in html or "taifood" in html or "sources" in html or "jwplayer" in html or "player" in html or "iframe" in html):
            print(f"      -> Trovato Server attivo: {serv}")
            return test_url

    print("      -> Nessuna firma riconosciuta, restituisco il Server 1 di default.")
    return f"{base_alba_url}?serv=1"

def resolve_player_url(source_url):
    """Trova l'URL del server attivo, con fallback aggressivi."""
    try:
        print(f"   -> Analisi URL: {source_url}")
        html = get_html(source_url)

        # 1. Cerca direttamente l'iframe di albaplayer nella pagina
        match_alba = re.search(r'<iframe.*?src=["\']([^"\']*albaplayer[^"\']*)["\']', html)

        # 2. Se non c'è, cerca il link Google Sites
        if not match_alba:
            match_google = re.search(r'https://www\.google\.com/url\?q=([^&"]+)', html)
            if match_google:
                blogger_url = urllib.parse.unquote(match_google.group(1))
                html_blogger = get_html(blogger_url, referer=source_url)
                match_alba = re.search(r'<iframe.*?src=["\']([^"\']*albaplayer[^"\']*)["\']', html_blogger)
                if not match_alba:
                    match_alba = re.search(r'<iframe.*?src=["\']([^"\']+)["\']', html_blogger)

        if match_alba:
            alba_url = match_alba.group(1)
            if alba_url.startswith('//'):
                alba_url = 'https:' + alba_url
            base_alba = alba_url.split('?')[0]
            return find_best_working_server(base_alba)

        # Fallback finale: restituiamo il link originale
        print("      -> Iframe non trovato, mantengo il link originario.")
        return source_url

    except Exception as e:
        print(f"      -> Errore risoluzione URL: {e}")
        return source_url

def parse_kosovari_matches():
    html = get_html(SOURCE_URL)
    if not html:
        return []

    matches = []
    try:
        # Aggiungiamo un parsing manuale (regex) come fallback se bs4 fallisce
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
            icon = icon_tag["src"] if icon_tag and icon_tag.get("src") else "https://raw.githubusercontent.com/TV-shqipp/tv-config-app/main/icon/sport.jpg"

            matches.append({"title": title, "link": link, "icon": icon})
    except Exception as e:
        print("Errore bs4:", e)

    return matches

def main():
    print("Scaricando le partite da kosovari.online...")
    raw_matches = parse_kosovari_matches()
    print(f"Trovate {len(raw_matches)} partite.")

    new_items = []
    for m in raw_matches:
        title = m['title']
        print(f"Verifica server per {title}...")
        player_url = resolve_player_url(m['link'])

        match_id = re.sub(r'[^a-zA-Z0-9-]', '', title.lower().replace(' ', '-'))

        if player_url:
            new_items.append({
                "id": f"sport-{match_id}",
                "name": title,
                "icon": m.get('icon', ""),
                "type": "dynamic_hls",
                "pageUrl": player_url,
                "referer": "https://kosovari.online/",
                "forceWeb": True
            })

    if not new_items:
        print("Nessuna partita elaborata.")
        return

    # Leggiamo il config.json
    try:
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception as e:
        print("Errore lettura config:", e)
        return

    # Troviamo la sezione Sport
    sport_section = next((s for s in data.get('sections', []) if s.get('id') == SPORT_SECTION_ID), None)
    if sport_section:
        # INVECE di sovrascrivere l'intera sezione (che cancella DamiTV),
        # andiamo a cercare SOLO il gruppo 'sport-kosovari'
        kosovari_group = next((i for i in sport_section.get('items', []) if i.get('id') == KOSOVARI_GROUP_ID), None)

        if kosovari_group:
            # Aggiorniamo solo le partite dentro Kosovari
            kosovari_group['items'] = new_items
        else:
            # Se il gruppo non c'è, lo creiamo (e lo aggiungiamo in cima, mantenendo gli altri tipo DamiTV)
            kosovari_group = {
                "id": KOSOVARI_GROUP_ID,
                "title": "Sport Kosovari",
                "subtitle": "AlbaPlayer / Server 1..7",
                "icon": "https://raw.githubusercontent.com/TV-shqipp/tv-config-app/main/icon/sport.jpg",
                "type": "group",
                "items": new_items
            }
            # Uniamo il nuovo gruppo alla lista esistente (così DamiTV non viene cancellato)
            sport_section['items'] = [kosovari_group] + [item for item in sport_section.get('items', []) if item.get('id') != KOSOVARI_GROUP_ID]

        # Aggiorniamo un sottotitolo generale se serve
        sport_section['subtitle'] = f"Eventi in diretta (aggiornati)"

        # Scriviamo il file
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

        print("config.json aggiornato con successo! (DamiTV salvato!)")

        path = os.environ.get("GITHUB_OUTPUT")
        if path:
            with open(path, "a", encoding="utf-8") as f:
                f.write("run=true\n")

if __name__ == '__main__':
    main()
