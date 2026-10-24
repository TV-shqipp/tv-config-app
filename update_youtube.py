import subprocess
import json
import os

# Canali YouTube da monitorare
CHANNELS = {
    "debat-plus": "https://www.youtube.com/@DukagjiniTV/live",
    "rtk1": "https://www.youtube.com/@RTKOfficial/live"
}

def get_direct_stream_url(youtube_url):
    try:
        # Usa yt-dlp per estrarre il link HLS diretto (.m3u8) della live
        cmd = ["yt-dlp", "-g", "--no-warnings", youtube_url]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=20)
        if result.returncode == 0:
            urls = result.stdout.strip().splitlines()
            if urls:
                return urls[0]
    except Exception as e:
        print(f"Errore con {youtube_url}: {e}")
    return None

def update_config():
    config_path = "config.json"
    if not os.path.exists(config_path):
        print("File config.json non trovato.")
        return

    with open(config_path, "r", encoding="utf-8") as f:
        config = json.load(f)

    updated = False
    for section in config.get("sections", []):
        for item in section.get("items", []):
            channel_id = item.get("id")
            if channel_id in CHANNELS:
                yt_url = CHANNELS[channel_id]
                print(f"Cerco la diretta per: {item['name']}...")
                direct_url = get_direct_stream_url(yt_url)
                if direct_url:
                    item["url"] = direct_url
                    item["type"] = "hls"  # Trasforma in flusso HLS nativo per ExoPlayer!
                    updated = True
                    print(f"Trovato! Link diretto inserito.")
                else:
                    print(f"Nessuna live attiva trovata al momento per {item['name']}.")

    if updated:
        with open(config_path, "w", encoding="utf-8") as f:
            json.dump(config, f, indent=2, ensure_ascii=False)
        print("config.json aggiornato con successo.")

if __name__ == "__main__":
    update_config()
