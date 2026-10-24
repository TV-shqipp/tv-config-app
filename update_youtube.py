import json
import sys
from datetime import datetime
from zoneinfo import ZoneInfo

import yt_dlp

YOUTUBE_URL = "https://www.youtube.com/@TopChannelAlbania/live"
ITEM_ID = "debat-plus"

TZ = ZoneInfo("Europe/Rome")
WINDOW_START = (19, 30)  # inizio controlli (ora italiana)
WINDOW_END = (21, 10)    # ultimo controllo utile (ora italiana)
OFFLINE_MESSAGE = "Ska debat sonte kap futja gjum se han rre"

FORCE = "--force" in sys.argv  # per test manuali: ignora la fascia oraria


def in_window():
    now = datetime.now(TZ)
    return WINDOW_START <= (now.hour, now.minute) <= WINDOW_END


def check_live():
    """Ritorna ('live', video_id, m3u8) | ('offline',) | ('error',)"""
    opts = {
        'format': 'best',
        'simulate': True,
        'quiet': True,
        'cookiefile': 'cookies.txt',
        'js_runtimes': {'node': {}},
        'extractor_args': {
            'youtube': {'player_client': ['web_safari', 'web']}
        },
    }
    try:
        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(YOUTUBE_URL, download=False)
    except Exception as e:
        msg = str(e).lower()
        print(f"yt-dlp: {e}")
        if "not currently live" in msg or "is not live" in msg:
            return ('offline',)
        return ('error',)  # errore vero (es. blocco bot): non toccare il config

    if not info.get('is_live'):
        return ('offline',)

    m3u8 = None
    for f in reversed(info.get('formats', [])):
        if '.m3u8' in (f.get('url') or '') or f.get('protocol', '').startswith('m3u8'):
            m3u8 = f['url']
            break
    m3u8 = m3u8 or info.get('manifest_url') or info.get('url')
    if not m3u8:
        return ('error',)
    return ('live', info.get('id'), m3u8)


def update_config(result):
    with open('config.json', 'r', encoding='utf-8') as f:
        data = json.load(f)

    changed = False
    for section in data.get('sections', []):
        for item in section.get('items', []):
            if item.get('id') != ITEM_ID:
                continue

            if result[0] == 'live':
                _, video_id, m3u8 = result
                # Stessa diretta già salvata: non rigenero il link (evita commit inutili)
                if item.get('type') == 'hls' and item.get('liveVideoId') == video_id:
                    continue
                item['type'] = 'hls'
                item['url'] = m3u8
                item['liveVideoId'] = video_id
                item.pop('message', None)
                item.pop('pageUrl', None)
                changed = True
            else:
                if item.get('type') == 'offline':
                    continue
                item['type'] = 'offline'
                item['message'] = OFFLINE_MESSAGE
                item.pop('url', None)
                item.pop('liveVideoId', None)
                changed = True

    if changed:
        with open('config.json', 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        print("config.json aggiornato.")
    else:
        print("Nessuna modifica necessaria.")


if __name__ == "__main__":
    if not FORCE and not in_window():
        print("Fuori dalla fascia 19:30-21:10, esco.")
        sys.exit(0)

    result = check_live()
    print(f"Esito: {result[0]}")
    if result[0] == 'error':
        sys.exit(0)  # lascio il config com'è
    update_config(result)
