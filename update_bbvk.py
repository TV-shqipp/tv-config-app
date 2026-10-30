import urllib.request
import re
import json
import ssl

ssl_ctx = ssl.create_default_context()
ssl_ctx.check_hostname = False
ssl_ctx.verify_mode = ssl.CERT_NONE

USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
# La pagina base del sito
TARGET_URL = "https://bbvipks.com/"

def fetch_html(url):
    req = urllib.request.Request(url, headers={'User-Agent': USER_AGENT})
    try:
        with urllib.request.urlopen(req, timeout=10, context=ssl_ctx) as resp:
            return resp.read().decode('utf-8', errors='ignore')
    except Exception as e:
        print(f"Errore: {e}")
        return ""

def main():
    html = fetch_html(TARGET_URL)
    
    # URL di default nel caso non riusciamo a fare scraping (così l'app non si rompe)
    base_player_url = "https://s1.bbvipks.com/"
    
    # 1. Cerca il dominio effettivo del player (es. s1.bbvipks.com o un nuovo dominio)
    iframes = re.findall(r'<iframe[^>]+src=["\']([^"\']+)["\']', html, re.IGNORECASE)
    for src in iframes:
        if src.startswith("//"):
            src = "https:" + src
        if ".php" in src and "bbvipks" in src:
            base_player_url = src.rsplit('/', 1)[0] + "/"
            break
            
    print(f"Base player URL trovato: {base_player_url}")

    # 2. Genera il blocco JSON per l'app
    final_channels = [
        {"name": "Kanali 1", "url": base_player_url + "k1.php"},
        {"name": "Kanali 1 HD", "url": base_player_url + "k1hd.php"},
        {"name": "Kanali 2", "url": base_player_url + "k2.php"},
        {"name": "Kanali 2 HD", "url": base_player_url + "k2hd.php"}
    ]
    
    items = []
    for ch in final_channels:
        safe_id = "bbvk-" + ch["name"].lower().replace(" ", "-")
        items.append({
            "id": safe_id,
            "name": ch["name"],
            "icon": "https://raw.githubusercontent.com/TV-shqipp/tv-config-app/main/icon/bbvk.png",
            "type": "dynamic_hls",
            "pageUrl": ch["url"],
            "referer": "https://bbvipks.com/",
            "forceWeb": True
        })
        
    # 3. Salva i risultati in un file JSON
    with open("bbvk_live.json", "w", encoding="utf-8") as f:
        json.dump(items, f, indent=2, ensure_ascii=False)
        
    print("bbvk_live.json generato con successo!")

if __name__ == "__main__":
    main()
