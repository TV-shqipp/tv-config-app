import json
import subprocess
import sys
import os

# Percorso del tuo config.json (assicurati che sia corretto per il tuo repository)
CONFIG_PATH = "app/src/main/assets/config.json"  # o "config.json" a seconda di dove lo hai messo

# Link del canale live di Dukagjini
CHANNEL_URL = "https://www.youtube.com/@DukagjiniTV/live"

def get_live_video_id(url):
    """Usa yt-dlp per estrarre solo l'ID del video, senza scaricare il flusso"""
    try:
        # --get-id dice a yt-dlp di stampare solo l'ID e uscire
        result = subprocess.run(
            ["yt-dlp", "--get-id", url],
            capture_output=True,
            text=True,
            check=True
        )
        video_id = result.stdout.strip()
        # Un ID di YouTube è lungo 11 caratteri
        if len(video_id) == 11:
            return video_id
        return None
    except subprocess.CalledProcessError as e:
        print(f"Errore durante l'estrazione dell'ID: {e}")
        return None

def update_config(video_id):
    """Legge, modifica e risalva il config.json"""
    if not os.path.exists(CONFIG_PATH):
        print(f"File non trovato: {CONFIG_PATH}")
        return

    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        config = json.load(f)

    updated = False
    for section in config.get("sections", []):
        for item in section.get("items", []):
            if item.get("id") == "debat-plus":
                if video_id:
                    item["url"] = video_id
                    updated = True
                    print(f"Trovata diretta! Nuovo ID: {video_id}")
                else:
                    print("Nessuna diretta trovata o ID non valido.")
                break

    if updated:
        with open(CONFIG_PATH, "w", encoding="utf-8") as f:
            json.dump(config, f, indent=2, ensure_ascii=False)
        print("config.json aggiornato con successo!")
    else:
        print("config.json non modificato.")

if __name__ == "__main__":
    print("Ricerca della diretta YouTube di Debat Plus...")
    new_video_id = get_live_video_id(CHANNEL_URL)
    update_config(new_video_id)
