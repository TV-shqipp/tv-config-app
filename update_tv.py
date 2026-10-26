import json
import urllib.request
from datetime import datetime
from zoneinfo import ZoneInfo

# 1. Funzione per controllare se un canale YouTube è attualmente in Diretta
def is_youtube_live(channel_url):
    try:
        req = urllib.request.Request(channel_url, headers={'User-Agent': 'Mozilla/5.0'})
        html = urllib.request.urlopen(req, timeout=10).read().decode('utf-8')
        # Se c't un link canonical watch?v= significa che c'è una diretta attiva in quel link
        return 'canonical" href="https://www.youtube.com/watch?v=' in html
    except Exception as e:
        print(f"Errore controllo YouTube {channel_url}: {e}")
        return False

def main():
    # Carica il file config.json
    with open('config.json', 'r', encoding='utf-8') as f:
        config = json.load(f)

    # Ottieni l'orario attuale in Kosovo/Albania
    tz = ZoneInfo("Europe/Tirane")
    now = datetime.now(tz)
    weekday = now.weekday() # 0 = Lunedì, 4 = Venerdì, 5 = Sabato
    hour = now.hour
    minute = now.minute

    alert_message = ""

    print(f"Controllo in corso... Ora locale: {hour}:{minute} (Giorno: {weekday})")

    # --- LOGICA 1: BASHKALLAJK (Venerdì dalle 20:40) ---
    if weekday == 4 and hour == 20 and minute >= 40:
        alert_message = "🔴 ORA IN DIRETTA: Bashkallajk su Klan Kosova!"
        # Se vuoi essere sicurissimo, puoi de-commentare il controllo YouTube:
        # if is_youtube_live("https://www.youtube.com/@KlanKosova/live"):
        #     alert_message = "🔴 ORA IN DIRETTA: Bashkallajk su Klan Kosova!"

    # --- LOGICA 2: NUSJA ME SHKOLLË (Sabato dalle 20:20) ---
    elif weekday == 5 and hour == 20 and minute >= 20:
        alert_message = "🔴 ORA IN DIRETTA: Nusja me Shkollë!"
    
    # --- LOGICA 3: DEBAT PLUS (Fascia serale generica, controlla YouTube Dukagjini) ---
    elif hour >= 20 and hour < 23:
        print("Controllo se Dukagjini è in live per Debat Plus...")
        if is_youtube_live("https://www.youtube.com/@RTVDukagjini/live"):
            alert_message = "🔴 ORA IN DIRETTA: Debat Plus su Dukagjini!"
            
            # Aggiorna anche il "nowPlaying" del canale specifico
            for section in config.get('sections', []):
                for item in section.get('items', []):
                    if item.get('id') == 'dukagjini':
                        item['nowPlaying'] = "Debat Plus"

    # Se non c'è nessuna live speciale, pulisci i messaggi
    if not alert_message:
        alert_message = ""
        # Pulisci il nowPlaying di Dukagjini se è finito
        for section in config.get('sections', []):
            for item in section.get('items', []):
                if item.get('id') == 'dukagjini':
                    item['nowPlaying'] = ""

    # Salva il global alert nel JSON
    config['globalAlert'] = alert_message

    # Scrivi il file modificato
    with open('config.json', 'w', encoding='utf-8') as f:
        json.dump(config, f, indent=2, ensure_ascii=False)
        
    print(f"Fatto! Alert impostato a: '{alert_message}'")

if __name__ == "__main__":
    main()
