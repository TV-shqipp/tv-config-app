import json
import urllib.request
from datetime import datetime
from zoneinfo import ZoneInfo

def is_youtube_live(channel_url):
    try:
        req = urllib.request.Request(channel_url, headers={'User-Agent': 'Mozilla/5.0'})
        html = urllib.request.urlopen(req, timeout=10).read().decode('utf-8')
        return 'canonical" href="https://www.youtube.com/watch?v=' in html
    except Exception as e:
        print(f"Errore controllo YouTube {channel_url}: {e}")
        return False

def update_now_playing(config, item_id, text):
    for section in config.get('sections', []):
        for item in section.get('items', []):
            if item.get('id') == item_id:
                item['nowPlaying'] = text
            if item.get('items'):
                for subitem in item['items']:
                    if subitem.get('id') == item_id:
                        subitem['nowPlaying'] = text

def main():
    with open('config.json', 'r', encoding='utf-8') as f:
        config = json.load(f)

    tz = ZoneInfo("Europe/Tirane")
    now = datetime.now(tz)
    weekday = now.weekday()
    hour = now.hour
    minute = now.minute

    alert_message = ""
    print(f"Controllo in corso... Ora locale: {hour}:{minute} (Giorno: {weekday})")

    # BASHKALLAJK (Venerdì 20:40 - 22:30)
    if weekday == 4 and (hour == 20 and minute >= 40) or (hour == 21) or (hour == 22 and minute <= 30):
        alert_message = "🔴 ORA IN DIRETTA: Bashkallajk su Klan Kosova!"
        update_now_playing(config, 'bashkallajk', "Bashkallajk (LIVE)")
    else:
        update_now_playing(config, 'bashkallajk', "")

    # NUSJA ME SHKOLLË (Sabato 20:20 - 22:30)
    if weekday == 5 and (hour == 20 and minute >= 20) or (hour == 21) or (hour == 22 and minute <= 30):
        alert_message = "🔴 ORA IN DIRETTA: Nusja me Shkollë!"
        update_now_playing(config, 'nusja-me-shkolle', "Nusja me shkollë (LIVE)")
    else:
        update_now_playing(config, 'nusja-me-shkolle', "")

    # DEBAT PLUS (Ogni giorno 20:00 - 23:00)
    if hour >= 20 and hour < 23:
        if is_youtube_live("https://www.youtube.com/@RTVDukagjini/live"):
            alert_message = "🔴 ORA IN DIRETTA: Debat Plus su Dukagjini!"
            update_now_playing(config, 'debat-plus', "Debat Plus")
    else:
        update_now_playing(config, 'debat-plus', "")

    config['globalAlert'] = alert_message

    with open('config.json', 'w', encoding='utf-8') as f:
        json.dump(config, f, indent=2, ensure_ascii=False)
        
    print(f"Fatto! Alert impostato a: '{alert_message}'")

if __name__ == "__main__":
    main()
