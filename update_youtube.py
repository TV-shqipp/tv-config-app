import yt_dlp
import json

YOUTUBE_URL = "https://www.youtube.com/@TopChannelAlbania/live"

def get_live_m3u8(url):
    ydl_opts = {
        'format': 'best',
        'simulate': True,
        'cookiefile': 'cookies.txt',
        'verbose': True,  # temporaneo: mostra i warning sul solver JS
        'js_runtimes': {'node': {}},
        'remote_components': ['ejs:github'],  # scarica il solver se manca/non combacia
        'extractor_args': {
            'youtube': {'player_client': ['web', 'tv']}
        },
    }
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            # Prima cerca un formato m3u8 tra quelli disponibili
            for f in reversed(info.get('formats', [])):
                if '.m3u8' in (f.get('url') or '') or f.get('protocol', '').startswith('m3u8'):
                    return f['url']
            return info.get('manifest_url') or info.get('url')
    except Exception as e:
        print(f"Errore durante l'estrazione: {e}")
        return None
