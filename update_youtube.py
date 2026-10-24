import yt_dlp
import json

# Mettiamo Top Channel Albania per il test
YOUTUBE_URL = "https://www.youtube.com/@TopChannelAlbania/live"

def get_live_m3u8(url):
    # Forza yt-dlp a restituire la Master Playlist HLS (.m3u8) combinata
    ydl_opts = {
        'format': 'best[protocol^=m3u8]', 
        'quiet': True,
        'simulate': True,
        'forceurl': True,
    }
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            
            # Se la diretta è attiva, restituisce il link .m3u8
            m3u8_url = info.get('url')
            if m3u8_url and '.m3u8' in m3u8_url:
                return m3u8_url
            
            # Fallback se l'url principale non è HLS, cerca nel manifest
            return info.get('manifest_url')
    except Exception as e:
        print(f"Errore durante l'estrazione: {e}")
        return None

def update_config(m3u8_url):
    with open('config.json', 'r') as file:
        data = json.load(file)

    for section in data.get('sections', []):
        for item in section.get('items', []):
            if item.get('id') == 'debat-plus':
                # Imposta come normale canale HLS compatibile con ExoPlayer
                item['type'] = 'hls'
                item['url'] = m3u8_url
                # Rimuove il vecchio sistema a iframe
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
