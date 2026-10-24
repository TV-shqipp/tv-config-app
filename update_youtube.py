import yt_dlp
import json

YOUTUBE_URL = "https://www.youtube.com/@TopChannelAlbania/live"


def get_live_m3u8(url):
    ydl_opts = {
        'format': 'best',
        'simulate': True,
        'cookiefile': 'cookies.txt',
        'verbose': True,  # temporaneo: toglilo quando funziona
        'js_runtimes': {'node': {}},
        'extractor_args': {
            'youtube': {'player_client': ['web_safari', 'web']}
        },
    }
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            # Cerca prima un formato HLS tra quelli disponibili
            for f in reversed(info.get('formats', [])):
                if '.m3u8' in (f.get('url') or '') or f.get('protocol', '').startswith('m3u8'):
                    return f['url']
            return info.get('manifest_url') or info.get('url')
    except Exception as e:
        print(f"Errore durante l'estrazione: {e}")
        return None


def update_config(m3u8_url):
    with open('config.json', 'r') as file:
        data = json.load(file)

    for section in data.get('sections', []):
        for item in section.get('items', []):
            if item.get('id') == 'debat-plus':
                item['type'] = 'hls'
                item['url'] = m3u8_url
                item.pop('pageUrl', None)

    with open('config.json', 'w') as file:
        json.dump(data, file, indent=2)


if __name__ == "__main__":
    live_url = get_live_m3u8(YOUTUBE_URL)
    if live_url:
        print("Link .m3u8 estratto con successo!")
        update_config(live_url)
    else:
        print("Nessuna diretta trovata al momento.")
