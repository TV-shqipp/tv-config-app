import json
import subprocess
import os
import sys

# 👇 ASSICURATI CHE QUESTO PERCORSO SIA CORRETTO 👇
CONFIG_PATH = "app/src/main/assets/config.json" 

CHANNEL_URL = "https://www.youtube.com/@DukagjiniTV/live"

def get_live_video_id(url):
    try:
        # Aggiungiamo un User-Agent finto per non farci riconoscere come bot
        cmd = [
            "yt-dlp",
            "--get-id",
            "--no-warnings",
            "--user-agent", "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
            url
        ]
        
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        video_id = result.stdout.strip()
        
        # Un ID di YouTube è lungo 11 caratteri
        if len(video_id) == 11:
            return video_id
        return None
    except subprocess.CalledProcessError as e:
        print(f"Errore durante l'estrazione (forse non c'è la diretta?): {e.stderr}")
        return None

def update_config(video_id):
    if not os.path.exists(CONFIG_PATH):
        print(f"❌ File non trovato: {CONFIG_PATH}")
        sys.exit(1) # Fa fallire l'azione se il file non c'è, così te ne accorgi

    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        config = json.load(f)

    updated = False
    for section in config.get("sections", []):
        for item in section.get("items", []):
            if item.get("id") == "debat-plus":
                if video_id:
                    item["url"] = video_id
                    updated = True
                    print(f"✅ Trovata diretta! Nuovo ID: {video_id}")
                else:
                    print("❌ Nessuna diretta trovata o canale offline. Il file resta invariato.")
                break

    if updated:
        with open(CONFIG_PATH, "w", encoding="utf-8") as f:
            json.dump(config, f, indent=2, ensure_ascii=False)
        print("✅ config.json aggiornato con successo!")
    else:
        print("Nessuna modifica necessaria.")

if __name__ == "__main__":
    print("Ricerca della diretta YouTube di Debat Plus...")
    new_video_id = get_live_video_id(CHANNEL_URL)
    update_config(new_video_id)
