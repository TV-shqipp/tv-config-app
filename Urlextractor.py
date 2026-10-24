import asyncio
import json
import os
from playwright.async_api import async_playwright

# 1. Configurazione dei canali da monitorare
# La chiave (es. "atv") DEVE corrispondere all'ID del canale nel tuo config.json
CANALI_DA_MONITORARE = {
    "radio-dukagjini": "https://video.gjirafa.com/radio-dukagjini",
    "rtv-21": "https://video.gjirafa.com/rtv-21-live",
    "ktv": "https://video.gjirafa.com/ktv-live",
    "atv": "https://video.gjirafa.com/atv-live-tv"
}

CONFIG_FILE = "config.json"

async def estrai_m3u8(page_url):
    """Estrae il link m3u8 usando Playwright."""
    captured_url = None

    async with async_playwright() as p:
        # Usiamo Chromium standard. Se dovesse fallire in futuro, 
        # si può passare a 'channel="chrome"' se Chrome è installato.
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )
        page = await context.new_page()

        # Intercetta le risposte di rete
        def handle_response(response):
            nonlocal captured_url
            # Cerchiamo file .m3u8 provenienti da gjirafa
            if ".m3u8" in response.url and "gjirafa" in response.url:
                if not captured_url:
                    captured_url = response.url
                    print(f"    [✓] Trovato: {captured_url}")

        page.on("response", handle_response)

        try:
            # Apriamo la pagina e aspettiamo che la rete si calmi (networkidle)
            await page.goto(page_url, wait_until="networkidle", timeout=30000)
            # Aspettiamo altri 3-5 secondi per dare tempo al player di avviarsi
            await page.wait_for_timeout(5000)
        except Exception as e:
            print(f"    [!] Errore caricamento {page_url}: {e}")
        finally:
            await browser.close()

    return captured_url

async def aggiorna_config():
    if not os.path.exists(CONFIG_FILE):
        print(f"Errore critico: file {CONFIG_FILE} non trovato!")
        return
        
    with open(CONFIG_FILE, "r", encoding="utf-8") as f:
        try:
            config = json.load(f)
        except json.JSONDecodeError:
            print("Errore: il file config.json non è un JSON valido.")
            return

    # Creiamo un dizionario per trovare velocemente i canali da modificare
    canali_config = {c.get("id"): c for c in config.get("channels", []) if "id" in c}

    aggiornamenti_fatti = False

    for canale_id, url_pagina in CANALI_DA_MONITORARE.items():
        print(f"\nControllo {canale_id} ({url_pagina})...")
        
        nuovo_link = await estrai_m3u8(url_pagina)
        
        if nuovo_link:
            if canale_id in canali_config:
                vecchio_link = canali_config[canale_id].get("url", "")
                if vecchio_link != nuovo_link:
                    print(f"    -> Aggiorno {canale_id} con il nuovo link.")
                    canali_config[canale_id]["url"] = nuovo_link
                    canali_config[canale_id]["type"] = "hls"
                    aggiornamenti_fatti = True
                else:
                    print(f"    -> Nessun cambiamento per {canale_id}.")
            else:
                print(f"    [!] Attenzione: ID '{canale_id}' non trovato nel config.json!")
        else:
            print(f"    [!] Nessun link trovato per {canale_id}. Mantengo il vecchio.")

    if aggiornamenti_fatti:
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(config, f, indent=2, ensure_ascii=False)
        print("\n✅ config.json aggiornato con successo!")
    else:
        print("\nNessun aggiornamento necessario.")

if __name__ == "__main__":
    asyncio.run(aggiorna_config())