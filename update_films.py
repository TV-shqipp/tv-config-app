name: Aggiorna Filma Shqip

on:
  schedule:
    # Gio/ven/sab: polling ogni 5 min nelle fasce serali
    - cron: '*/5 17-22 * * 4,5,6'
    # Resto della settimana: ogni 15 min per refresh e recuperi
    - cron: '*/15 * * * *'
  workflow_dispatch:
    inputs:
      force:
        description: 'Test: cerca subito l ultimo film di ogni canale'
        type: boolean
        default: false

concurrency:
  group: config-update
  cancel-in-progress: false

permissions:
  contents: write

jobs:
  update-films:
    runs-on: ubuntu-latest
    env:
      FORCE: ${{ inputs.force }}
    steps:
      - uses: actions/checkout@v4

      - uses: actions/setup-python@v5
        with:
          python-version: '3.12'

      - name: Decidi se c e qualcosa da fare
        id: gate
        run: python update_films.py --plan

      - name: Configura Node.js
        if: steps.gate.outputs.run == 'true'
        uses: actions/setup-node@v4
        with:
          node-version: '24'

      - name: Installa ffmpeg (utile a yt-dlp per HLS/DASH)
        if: steps.gate.outputs.run == 'true'
        run: sudo apt-get update && sudo apt-get install -y ffmpeg

      - name: Installa yt-dlp e il solver JS
        if: steps.gate.outputs.run == 'true'
        run: pip install --upgrade "yt-dlp[default]" yt-dlp-ejs

      - name: Crea il file dei cookie dal Secret
        if: steps.gate.outputs.run == 'true'
        env:
          YT_COOKIES: ${{ secrets.YT_COOKIES }}
        run: printf '%s\n' "$YT_COOKIES" > cookies.txt

      - name: Esegui lo script
        if: steps.gate.outputs.run == 'true'
        run: python update_films.py

      - name: Log config (debug)
        if: steps.gate.outputs.run == 'true'
        run: |
          python -c "import json; d=json.load(open('config.json')); \
          print(json.dumps([s for sec in d['sections'] if sec['id']=='tv' \
          for s in sec['items'] if s['id']=='filma-shqip'][0], indent=2, ensure_ascii=False))"

      - name: Salva il config su GitHub
        if: steps.gate.outputs.run == 'true'
        run: |
          git config --global user.name "GitHub Action Bot"
          git config --global user.email "action@github.com"
          git add config.json
          if git diff --staged --quiet; then
            echo "Nessuna modifica da committare."
          else
            git commit -m "Aggiornati film Filma Shqip"
            for attempt in 1 2 3 4 5; do
              if git pull --rebase origin main && git push; then exit 0; fi
              git rebase --abort 2>/dev/null || true
              sleep $((attempt * 5))
            done
            exit 1
          fi
