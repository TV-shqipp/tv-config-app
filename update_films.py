"""Filma Shqip: tiene aggiornati nel config.json i link dei film presi da YouTube.

Regole:
- Film CARICATI (Edhe malet flasin, Rrugët e Lirisë):
  * cerca il video per 10 minuti dall'orario indicato, poi smette;
  * dopo 1h30 fa UN ricontrollo e sostituisce il video con quello nuovo;
  * poi rinnova il link ogni REFRESH_HOURS ore fino alla settimana dopo.
- Film in DIRETTA (Bashkallajk, Nusja me shkollë):
  * fino all'inizio della diretta resta il video vecchio;
  * all'orario cerca la diretta e la mette dentro;
  * dopo 2 ore cerca il video registrato e lo sostituisce (riprova finché la
    diretta non è finita), poi rinnova il link ogni REFRESH_HOURS ore.
- Qualità: HLS fino a 1080p. YouTube offre video e audio HLS separati, quindi
  il link salvato punta al Cloudflare Worker, che costruisce il master
  (?v=...&a=...). Per le dirette si usa il manifest adattivo di YouTube.
- Nessun download, nessun merge, nessun hosting: solo URL.
"""

import json
import os
import re
import sys
import unicodedata
from datetime import datetime, timedelta, timezone
from urllib.parse import quote
from zoneinfo import ZoneInfo

CONFIG_FILE = "config.json"
GROUP_ID = "filma-shqip"
TZ = ZoneInfo("Europe/Rome")
UTC = timezone.utc

# ---------------------------------------------------------------- impostazioni
REFRESH_HOURS = 3           # i link YouTube durano ~6h: 3h lascia margine per un film intero
RECHECK_SPAN_MIN = 30       # finestra in cui si può fare il ricontrollo programmato
LIVE_RECHECK_MAX_MIN = 360  # le dirette: smetto di cercare il registrato dopo 6h
RETRY_MIN = 10              # pausa minima tra due tentativi di ricontrollo

MAX_HEIGHT = 1080

WORKER_URL = "https://tvshqip.ardit-asllanaj-2003.workers.dev/"

OFFLINE_MESSAGE = "Il film di questa settimana non è ancora disponibile.\nRiprova più tardi."

# window: minuti di ricerca dopo l'orario (solo caricati)
# recheck_after: minuti dopo l'orario per il ricontrollo che sostituisce il video
FILMS = [
    {"id": "edhe-malet-flasin", "name": "Edhe malet flasin",
     "channel": "@EdaFilms2", "day": 5, "time": "20:31",
     "live": False, "window": 10, "recheck_after": 90,
     "keywords": ["edhe malet flasin"], "exclude": ["promo"]},
    {"id": "rrugt-e-lirise", "name": "Rrugët e Lirisë",
     "channel": "@ProduksioniDONJETA", "day": 4, "time": "20:00",
     "live": False, "window": 10, "recheck_after": 90,
     "keywords": ["rrugët e lirisë"], "exclude": ["promo"]},
    {"id": "bashkallajk", "name": "Bashkallajk",
     "channel": "@teve1", "day": 4, "time": "20:45",
     "live": True, "recheck_after": 120,
     "keywords": ["bashkallajk"], "exclude": ["promo"]},
    {"id": "nusja-me-shkolle", "name": "Nusja me shkollë",
     "channel": "@DTVOff", "day": 5, "time": "20:30",
     "live": True, "recheck_after": 120,
     "keywords": ["nusja me shkollë"], "exclude": ["promo"]},
]

FORCE = os.environ.get("FORCE", "").lower() == "true" or "--force" in sys.argv
PLAN = "--plan" in sys.argv


# --------------------------------------------------------------------- utilità
def norm(text):
    text = unicodedata.normalize("NFKD", text or "")
    text = "".join(c for c in text if not unicodedata.combining(c))
    text = re.sub(r"[^\w\s]", " ", text.lower())
    return re.sub(r"\s+", " ", text).strip()


def title_ok(title, film):
    t = norm(title)
    if not all(norm(k) in t for k in film["keywords"]):
        return False
    return not any(norm(x) in t for x in film["exclude"])


def minutes_between(a, b):
    return (a.astimezone(UTC) - b.astimezone(UTC)).total_seconds() / 60


def iso(dt):
    return dt.astimezone(UTC).isoformat(timespec="seconds")


def parse_iso(text):
    try:
        return datetime.fromisoformat(text)
    except (TypeError, ValueError):
        return None


def last_occurrence(day, hhmm, now):
    h, m = map(int, hhmm.split(":"))
    cand = now.replace(hour=h, minute=m, second=0, microsecond=0)
    cand -= timedelta(days=(now.weekday() - day) % 7)
    if cand > now:
        cand -= timedelta(days=7)
    return cand


def throttled(item, now, gap_min):
    last = parse_iso(item.get("lastTry"))
    return last is not None and minutes_between(now, last) < gap_min


def proxy_url(url):
    """URL del proxy Cloudflare per un singolo URL (manifest adattivo, fallback)."""
    if not url:
        return url
    return f"{WORKER_URL}?url={quote(url, safe='')}"


def pair_url(video, audio):
    """URL del Worker che unisce un HLS video-only e uno audio-only in un master."""
    height = video.get("height") or 1080
    width = video.get("width") or round(height * 16 / 9)
    bw = int(((video.get("tbr") or 5000) + 160) * 1000)
    return (f"{WORKER_URL}?v={quote(video['url'], safe='')}"
            f"&a={quote(audio['url'], safe='')}"
            f"&res={width}x{height}&bw={bw}")


# --------------------------------------------------------------------- config
def load_config():
    with open(CONFIG_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def save_config(data):
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def ensure_group(data):
    tv = next((s for s in data.get("sections", []) if s.get("id") == "tv"), None)
    if tv is None:
        return False
    changed = False
    items = tv.setdefault("items", [])
    group = next((i for i in items if i.get("id") == GROUP_ID), None)
    if group is None:
        group = {"id": GROUP_ID, "title": "Filma Shqip", "subtitle": "Filme shqiptare",
                 "icon": "", "type": "group", "items": []}
        items.append(group)
        changed = True
    sub = group.setdefault("items", [])
    for film in FILMS:
        if not any(i.get("id") == film["id"] for i in sub):
            sub.append({"id": film["id"], "name": film["name"], "icon": "",
                        "type": "offline", "message": OFFLINE_MESSAGE})
            changed = True
    return changed


def find_item(data, item_id):
    for section in data.get("sections", []):
        for item in section.get("items", []):
            if item.get("id") == GROUP_ID:
                for sub in item.get("items", []):
                    if sub.get("id") == item_id:
                        return sub
    return None


# ------------------------------------------------------------ cosa c'è da fare
def refresh_needed(item, now):
    """Rinnova il link (stesso videoId) ogni REFRESH_HOURS ore."""
    if item.get("type") != "hls" or not item.get("videoId"):
        return False
    updated = parse_iso(item.get("linkUpdated"))
    if updated is None:
        return True
    return minutes_between(now, updated) >= REFRESH_HOURS * 60


def due_task(film, item, now):
    """Restituisce 'search', 'recheck' o None.

    item['week']    = settimana (orario programmato) per cui c'è un video trovato
    item['recheck'] = settimana per cui il ricontrollo programmato è già fatto
    """
    sched = last_occurrence(film["day"], film["time"], now)
    wk = sched.isoformat()
    since = minutes_between(now, sched)
    after = film["recheck_after"]

    if film["live"]:
        # Fase 1: attesa della diretta (fino al ricontrollo delle 2 ore)
        if item.get("week") != wk and since < after:
            return "search"
        # Fase 2: dopo 2 ore il video registrato, si riprova finché la diretta non finisce
        if (item.get("recheck") != wk and after <= since <= LIVE_RECHECK_MAX_MIN
                and not throttled(item, now, RETRY_MIN)):
            return "recheck"
        return None

    # Caricati: 10 minuti di ricerca, poi un solo ricontrollo a 1h30
    if item.get("week") != wk and since <= film["window"]:
        return "search"
    if item.get("recheck") != wk and after <= since <= after + RECHECK_SPAN_MIN:
        return "recheck"
    return None


# --------------------------------------------------------------------- YouTube
def base_opts():
    # Nessun override di player_client: stessi client del test `yt-dlp -F`,
    # che restituisce gli HLS video-only (270) e audio-only (233/234).
    return {
        "format": "best",
        "simulate": True,
        "quiet": True,
        "noprogress": True,
        "no_warnings": True,
        "cookiefile": "cookies.txt",
        "js_runtimes": {"node": {}},
    }


def extract(url):
    import yt_dlp
    opts = base_opts()
    opts["ignore_no_formats_error"] = True
    with yt_dlp.YoutubeDL(opts) as ydl:
        return ydl.extract_info(url, download=False)


def list_channel(film, tab):
    import yt_dlp
    url = f"https://www.youtube.com/{film['channel']}/{tab}"
    opts = base_opts()
    opts.update({"extract_flat": "in_playlist", "playlistend": 50})
    with yt_dlp.YoutubeDL(opts) as ydl:
        info = ydl.extract_info(url, download=False)
    return [e for e in ((info or {}).get("entries") or []) if e and e.get("id")]


def _is_hls(f):
    return f.get("protocol") in ("m3u8", "m3u8_native") and bool(f.get("url"))


def _has_video(f):
    return f.get("vcodec") not in (None, "none")


def _has_audio(f):
    return f.get("acodec") not in (None, "none")


def _fid(f):
    m = re.match(r"\d+", str(f.get("format_id", "")))
    return int(m.group()) if m else 0


def pick_stream(info):
    """Restituisce l'URL da salvare nel config (già passato dal Worker)."""
    formats = info.get("formats") or []
    live = info.get("live_status") == "is_live" or info.get("is_live")
    heights = sorted({f.get("height") for f in formats if f.get("height")})
    print(f"  altezze disponibili: {heights}")

    # 1. Dirette: manifest adattivo di YouTube (video+audio, più qualità).
    manifest = info.get("manifest_url")
    if live and manifest and ".m3u8" in manifest:
        print("  diretta: manifest HLS adattivo")
        return proxy_url(manifest)

    # 2. VOD: HLS video-only (migliore <= 1080p, meglio H.264) + HLS audio-only.
    videos = [f for f in formats if _is_hls(f) and _has_video(f) and not _has_audio(f)
              and (f.get("height") or 0) <= MAX_HEIGHT]
    audios = [f for f in formats if _is_hls(f) and _has_audio(f) and not _has_video(f)]
    if videos and audios:
        videos.sort(key=lambda f: (f.get("height") or 0,
                                   str(f.get("vcodec", "")).startswith("avc1"),
                                   f.get("tbr") or 0), reverse=True)

        def audio_rank(f):
            note = str(f.get("format_note") or "").lower()
            return ("high" in note, "medium" in note, f.get("abr") or f.get("tbr") or 0, _fid(f))

        audios.sort(key=audio_rank, reverse=True)
        v, a = videos[0], audios[0]
        print(f"  HLS video {v.get('height')}p ({v.get('format_id')}) "
              f"+ audio ({a.get('format_id')})")
        return pair_url(v, a)

    # 3. HLS già muxato, se esiste.
    muxed_hls = [f for f in formats if _is_hls(f) and _has_video(f) and _has_audio(f)
                 and (f.get("height") or 0) <= MAX_HEIGHT]
    if muxed_hls:
        muxed_hls.sort(key=lambda f: f.get("height") or 0, reverse=True)
        best = muxed_hls[0]
        print(f"  HLS muxato {best.get('height')}p")
        return proxy_url(best["url"])

    # 4. Ultima spiaggia: MP4 progressivo (di solito 360p).
    muxed = [f for f in formats if str(f.get("protocol", "")).startswith("http")
             and _has_video(f) and _has_audio(f) and (f.get("height") or 0) <= MAX_HEIGHT]
    if muxed:
        muxed.sort(key=lambda f: f.get("height") or 0, reverse=True)
        best = muxed[0]
        print(f"  ATTENZIONE: solo MP4 progressivo {best.get('height')}p")
        return proxy_url(best["url"])

    return proxy_url(info.get("url"))


def video_ts(info):
    ts = info.get("release_timestamp") or info.get("timestamp")
    if ts:
        return ts
    date = info.get("upload_date")
    if date:
        try:
            day = datetime.strptime(date, "%Y%m%d").replace(tzinfo=TZ)
            return (day + timedelta(days=1)).timestamp() - 1
        except ValueError:
            pass
    return None


def search_video(film, min_ts):
    """Cerca il video della settimana in /videos e /streams."""
    tabs = ("streams", "videos") if film["live"] else ("videos", "streams")
    for tab in tabs:
        try:
            entries = list_channel(film, tab)
        except Exception as e:
            print(f"  errore lettura tab {tab}: {e}")
            continue

        for entry in entries:
            if not title_ok(entry.get("title"), film):
                continue
            if entry.get("live_status") == "is_upcoming":
                print(f"  premiere programmata: {entry.get('title')} (salto)")
                continue

            try:
                info = extract(f"https://www.youtube.com/watch?v={entry['id']}")
            except Exception as e:
                print(f"  errore estrazione: {e}")
                continue

            if info.get("live_status") == "is_upcoming":
                continue

            ts = video_ts(info)
            if ts is not None and ts < min_ts:
                print(f"  video vecchio saltato: {info.get('title')}")
                continue

            url = pick_stream(info)
            if not url:
                print("  video trovato ma senza flusso utilizzabile")
                continue

            return info, url

    return None, None


def set_link(item, info, url, now):
    item["type"] = "hls"
    item["url"] = url
    item["videoId"] = info.get("id")
    item["videoTitle"] = info.get("title")
    live = info.get("live_status") == "is_live" or info.get("is_live")
    item["state"] = "live" if live else "vod"
    item["linkUpdated"] = iso(now)
    item.pop("message", None)
    item.pop("pageUrl", None)


def do_refresh(item, now):
    info = extract(f"https://www.youtube.com/watch?v={item['videoId']}")
    url = pick_stream(info)
    if not url:
        print("  rinnovo fallito: nessun flusso, tengo il link vecchio")
        return
    set_link(item, info, url, now)
    print("  link rinnovato")


def run_task(film, item, task, now):
    sched = last_occurrence(film["day"], film["time"], now)
    wk = sched.isoformat()

    if task == "refresh":
        do_refresh(item, now)
        return

    item["lastTry"] = iso(now)
    if FORCE:
        min_ts = (now - timedelta(days=30)).timestamp()
    else:
        min_ts = (sched - timedelta(hours=3)).timestamp()

    info, url = search_video(film, min_ts)

    if task == "search":
        if not info:
            print("  nessun video nuovo trovato")
            return
        set_link(item, info, url, now)
        item["week"] = wk
        print(f"  video trovato: {info.get('title')} ({item['state']})")
        return

    # task == "recheck": sostituisce il video vecchio con quello nuovo
    if not info:
        print("  ricontrollo: nessun video trovato")
        if not film["live"]:
            item["recheck"] = wk  # un solo tentativo per i caricati
        return
    set_link(item, info, url, now)
    item["week"] = wk
    print(f"  ricontrollo: {info.get('title')} ({item['state']})")
    if not (film["live"] and item["state"] == "live"):
        item["recheck"] = wk  # per le dirette si riprova finché è ancora in onda


# ------------------------------------------------------------------------ main
def write_output(run):
    path = os.environ.get("GITHUB_OUTPUT")
    if path:
        with open(path, "a", encoding="utf-8") as f:
            f.write(f"run={'true' if run else 'false'}\n")


def main():
    now = datetime.now(TZ)
    data = load_config()
    changed = ensure_group(data)

    work = []
    for film in FILMS:
        item = find_item(data, film["id"])
        if item is None:
            continue
        task = "search" if FORCE else due_task(film, item, now)
        if task is None and refresh_needed(item, now):
            task = "refresh"
        if task:
            work.append((film, item, task))

    print(f"Ora italiana: {now:%Y-%m-%d %H:%M}")
    for film, _, task in work:
        print(f"- {film['name']}: {task}")
    run = bool(work) or changed

    if PLAN:
        if not run:
            print("Niente da fare.")
        write_output(run)
        return

    if not run:
        print("Niente da fare.")
        return

    errors = 0
    for film, item, task in work:
        print(f"[{film['name']}] {task}")
        before = json.dumps(item, sort_keys=True)
        try:
            run_task(film, item, task, now)
        except Exception as e:
            errors += 1
            print(f"  errore: {e}")
        if task != "refresh" and refresh_needed(item, now):
            try:
                do_refresh(item, now)
            except Exception as e:
                errors += 1
                print(f"  errore nel rinnovo: {e}")
        if json.dumps(item, sort_keys=True) != before:
            changed = True

    if changed:
        save_config(data)
        print("config.json aggiornato.")
    else:
        print("Nessuna modifica necessaria.")

    if work and errors == len(work):
        print("Tutti i task sono falliti: controlla cookies/yt-dlp.")
        sys.exit(1)


if __name__ == "__main__":
    main()
