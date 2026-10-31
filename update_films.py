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

# Come viene salvato il film nel config.json:
#   "id"  -> solo il videoId (url vuoto): è l'app sulla TV a ottenere il flusso sul
#            proprio IP. Nessuna estrazione dei formati da GitHub, quindi niente
#            blocchi anti-bot e niente link che scadono.
#   "hls" -> vecchio metodo: link HLS/MP4 estratto qui e passato dal Worker.
LINK_MODE = "id"

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


FILM_ICONS = {
    "edhe-malet-flasin": "https://raw.githubusercontent.com/TV-shqipp/tv-config-app/main/icon/edhemalet.jpg",
    "rrugt-e-lirise": "https://raw.githubusercontent.com/TV-shqipp/tv-config-app/main/icon/rrugeteliris.jpg",
    "bashkallajk": "https://raw.githubusercontent.com/TV-shqipp/tv-config-app/main/icon/bashkallajk.jpg",
    "nusja-me-shkolle": "https://raw.githubusercontent.com/TV-shqipp/tv-config-app/main/icon/nusjameshkoll.jpg",
}

SECTION_ICON = "https://raw.githubusercontent.com/TV-shqipp/tv-config-app/main/icon/filmashqip.jpg"


def ensure_group(data):
    changed = False
    sections = data.setdefault("sections", [])

    # 1. Se filma-shqip è stato inserito dentro 'tv' per errore, lo rimuoviamo
    tv = next((s for s in sections if s.get("id") == "tv"), None)
    if tv and "items" in tv:
        old_len = len(tv["items"])
        tv["items"] = [i for i in tv["items"] if i.get("id") != GROUP_ID]
        if len(tv["items"]) != old_len:
            changed = True

    # 2. Cerca o crea la sezione principale 'filma-shqip' tra i grandi gruppi esterni
    section = next((s for s in sections if s.get("id") == GROUP_ID), None)
    if section is None:
        section = {
            "id": GROUP_ID,
            "title": "Filma Shqip",
            "subtitle": "Filme shqiptare",
            "icon": SECTION_ICON,
            "items": []
        }
        sections.append(section)
        changed = True

    sub = section.setdefault("items", [])
    for film in FILMS:
        item = next((i for i in sub if i.get("id") == film["id"]), None)
        icon = FILM_ICONS.get(film["id"], "")
        if item is None:
            sub.append({
                "id": film["id"],
                "name": film["name"],
                "icon": icon,
                "type": "offline",
                "message": OFFLINE_MESSAGE
            })
            changed = True
        elif not item.get("icon") and icon:
            item["icon"] = icon
            changed = True

    return changed


def find_item(data, item_id):
    for section in data.get("sections", []):
        if section.get("id") == GROUP_ID:
            for item in section.get("items", []):
                if item.get("id") == item_id:
                    return item
    return None


# ------------------------------------------------------------ cosa c'è da fare
def refresh_needed(item, now):
    """Rinnova il link (stesso videoId) ogni REFRESH_HOURS ore."""
    if item.get("type") != "hls" or not item.get("videoId"):
        return False
    if LINK_MODE == "id":
        # Niente da rinnovare: serve solo ripulire un vecchio url rimasto nel config.
        return bool(item.get("url"))
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


class _Log:
    """Raccoglie gli avvisi di yt-dlp: spiegano perché non ci sono formati."""

    def __init__(self):
        self.msgs = []

    def debug(self, m):
        pass

    def info(self, m):
        pass

    def warning(self, m):
        self.msgs.append(str(m))

    def error(self, m):
        self.msgs.append(str(m))


def extract(url, clients=None, cookies=True, meta_only=False):
    """Estrae le info di un video. clients=None usa i client predefiniti di yt-dlp."""
    import yt_dlp
    opts = base_opts()
    opts["ignore_no_formats_error"] = True
    log = _Log()
    opts["logger"] = log
    ea = {}
    if clients:
        ea["player_client"] = clients
    if meta_only:
        ea["player_skip"] = ["js"]  # titolo/data/stato bastano: niente solver JS (lento)
    if ea:
        opts["extractor_args"] = {"youtube": ea}
    if not cookies:
        opts.pop("cookiefile", None)  # il client ios non supporta i cookie
    with yt_dlp.YoutubeDL(opts) as ydl:
        info = ydl.extract_info(url, download=False)
    if isinstance(info, dict):
        info["_msgs"] = log.msgs
    return info


# Client provati in ordine finché non esce un HLS video+audio.
# Dal runner GitHub (IP datacenter) i client predefiniti possono non dare formati.
CLIENT_TRIES = [None, ["ios"], ["tv"], ["mweb"], ["web_safari", "web"]]


def has_hls_pair(info):
    fm = info.get("formats") or []
    return (any(_is_hls(f) and _has_video(f) and not _has_audio(f) for f in fm)
            and any(_is_hls(f) and _has_audio(f) and not _has_video(f) for f in fm))


def extract_best(url):
    """Prova i client uno dopo l'altro e restituisce le info migliori."""
    best = None
    for clients in CLIENT_TRIES:
        label = ",".join(clients) if clients else "default"
        try:
            info = extract(url, clients, cookies=(clients != ["ios"]))
        except Exception as e:
            print(f"  client {label}: errore {str(e)[:150]}")
            continue
        fm = info.get("formats") or []
        n_hls = sum(1 for f in fm if _is_hls(f))
        print(f"  client {label}: {len(fm)} formati, {n_hls} HLS")
        msgs = [m for m in (info.get("_msgs") or []) if m]
        if not fm and msgs:
            print(f"    motivo: {msgs[0][:300]}")
            if any(k in " ".join(msgs) for k in ("not a bot", "Sign in", "cookies")):
                print("  YouTube blocca la richiesta (cookie scaduti o IP bloccato): "
                      "inutile provare altri client.")
                return info
        if info.get("live_status") == "is_upcoming":
            return info
        if info.get("live_status") == "is_live" and info.get("manifest_url"):
            return info
        if has_hls_pair(info):
            return info
        if best is None or len(fm) > len(best.get("formats") or []):
            best = info
    return best


def list_channel(film, tab, limit=50):
    """Elenco dei video di una tab del canale (più recenti per primi).
    tab="search:parola" cerca dentro il canale (utile se i video sono tanti)."""
    import yt_dlp
    if tab.startswith("search:"):
        url = f"https://www.youtube.com/{film['channel']}/search?query={quote(tab[7:])}"
    else:
        url = f"https://www.youtube.com/{film['channel']}/{tab}"
    opts = base_opts()
    opts.update({"extract_flat": "in_playlist", "playlistend": limit})
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


def _fetch_meta(watch):
    """Titolo, data e stato del video (lettura veloce, con ripiego su quella normale)."""
    try:
        return extract(watch, meta_only=True)
    except Exception:
        return extract(watch)


def _stream_for(info, watch):
    """Dal video giusto ricava cosa scrivere nel config ('' in modalità id)."""
    if LINK_MODE == "id":
        print(f"  salvo solo il videoId {info.get('id')}: {info.get('title')}")
        return info, ""

    is_live = info.get("live_status") == "is_live" or info.get("is_live")
    ok = has_hls_pair(info) or (is_live and info.get("manifest_url"))
    if not ok:
        try:
            info = extract_best(watch) or info
        except Exception as e:
            print(f"  errore estrazione: {e}")
            return None, None

    url = pick_stream(info)
    if not url:
        print("  video trovato ma senza flusso utilizzabile: mi fermo")
        return None, None
    return info, url


def search_video(film, min_ts):
    """Cerca il video della settimana: prima nelle tab del canale, poi con la ricerca."""
    # I canali dei film caricati non hanno la tab /streams (errore inutile).
    tabs = ("streams", "videos") if film["live"] else ("videos",)
    for tab in tabs:
        try:
            entries = list_channel(film, tab)
        except Exception as e:
            print(f"  errore lettura tab {tab}: {e}")
            continue

        matches = [e for e in entries if title_ok(e.get("title"), film)]
        print(f"  tab {tab}: {len(entries)} video, {len(matches)} col titolo giusto")

        for entry in matches:
            if entry.get("live_status") == "is_upcoming":
                print(f"  premiere programmata: {entry.get('title')} (salto)")
                continue

            watch = f"https://www.youtube.com/watch?v={entry['id']}"
            try:
                info = _fetch_meta(watch)
            except Exception as e:
                print(f"  errore estrazione: {e}")
                continue

            if info.get("live_status") == "is_upcoming":
                continue

            ts = video_ts(info)
            if ts is not None and ts < min_ts:
                print(f"  video vecchio saltato: {info.get('title')} (mi fermo qui)")
                break  # l'elenco è dal più recente: i successivi sono ancora più vecchi

            return _stream_for(info, watch)

    # Ripiego: ricerca dentro il canale. Serve quando il canale carica tanti video
    # e quello cercato è oltre i primi 50. I risultati non sono in ordine di data:
    # si guardano i primi e si sceglie il più recente.
    key = film["keywords"][0]
    try:
        entries = list_channel(film, f"search:{key}", limit=15)
    except Exception as e:
        print(f"  errore nella ricerca nel canale: {e}")
        return None, None

    matches = [e for e in entries if title_ok(e.get("title"), film)]
    print(f"  ricerca nel canale '{key}': {len(entries)} risultati, "
          f"{len(matches)} col titolo giusto")

    best, best_ts = None, -1
    for entry in matches[:10]:
        if entry.get("live_status") == "is_upcoming":
            continue
        try:
            info = _fetch_meta(f"https://www.youtube.com/watch?v={entry['id']}")
        except Exception as e:
            print(f"  errore estrazione: {e}")
            continue
        if info.get("live_status") == "is_upcoming":
            continue
        ts = video_ts(info)
        if ts is not None and ts < min_ts:
            continue
        if (ts or 0) > best_ts:
            best, best_ts = info, ts or 0

    if best is None:
        return None, None
    print(f"  trovato con la ricerca: {best.get('title')}")
    return _stream_for(best, f"https://www.youtube.com/watch?v={best['id']}")


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
    if not item.get("icon") and item.get("id") in FILM_ICONS:
        item["icon"] = FILM_ICONS[item["id"]]


def do_refresh(item, now):
    if LINK_MODE == "id":
        item["url"] = ""  # l'app userà il videoId
        item["linkUpdated"] = iso(now)
        print("  url vecchio rimosso: l'app userà il videoId")
        return
    info = extract_best(f"https://www.youtube.com/watch?v={item['videoId']}")
    url = pick_stream(info) if info else None
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
