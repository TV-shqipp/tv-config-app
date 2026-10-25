"""Filma Shqip: tiene aggiornati nel config.json i link dei film presi da YouTube.

Strategia:
- Tutti i flussi (VOD, live, premiere) usano HLS (m3u8), che contiene già le
  varianti di qualità e permette al player di scegliere dinamicamente.
- Limite massimo di altezza: 1080p, per evitare bitrate troppo alti che
  causerebbero buffering sulla TV.
- Tutti gli URL vengono passati attraverso un Cloudflare Worker che fa da proxy,
  evitando i blocchi IP di YouTube.
- Nessun download, nessun merge, nessun hosting: solo URL diretti.
"""

import json
import os
import re
import sys
import unicodedata
import urllib.request
from datetime import datetime, timedelta, timezone
from urllib.parse import quote
from zoneinfo import ZoneInfo

CONFIG_FILE = "config.json"
GROUP_ID = "filma-shqip"
TZ = ZoneInfo("Europe/Rome")
UTC = timezone.utc

# ---------------------------------------------------------------- impostazioni
REFRESH_HOURS = 3
EXPIRE_MARGIN_MIN = 120
RECHECK_UPLOAD_MIN = 90
RETRY_MIN = 10
CATCHUP_MAX_MIN = 72 * 60

MAX_HEIGHT = 1080  # tetto massimo di risoluzione per evitare buffering

# URL del tuo Cloudflare Worker
WORKER_URL = "https://tvshqip.ardit-asllanaj-2003.workers.dev/"

OFFLINE_MESSAGE = "Il film di questa settimana non è ancora disponibile.\nRiprova più tardi."

FILMS = [
    {"id": "edhe-malet-flasin", "name": "Edhe malet flasin",
     "channel": "@EdaFilms2", "day": 5, "time": "20:31", "window": 10,
     "keywords": ["edhe malet flasin"], "exclude": ["promo"]},
    {"id": "rrugt-e-lirise", "name": "Rrugët e Lirisë",
     "channel": "@ProduksioniDONJETA", "day": 4, "time": "20:00", "window": 10,
     "keywords": ["rrugët e lirisë"], "exclude": ["promo"]},
    {"id": "bashkallajk", "name": "Bashkallajk",
     "channel": "@teve1", "day": 4, "time": "20:45",
     "keywords": ["bashkallajk"], "exclude": ["promo"]},
    {"id": "nusja-me-shkolle", "name": "Nusja me shkollë",
     "channel": "@DTVOff", "day": 5, "time": "20:30",
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


def expire_of(url):
    m = re.search(r"/expire/(\d+)", url or "") or re.search(r"[?&]expire=(\d+)", url or "")
    return int(m.group(1)) if m else None


def throttled(item, now, gap_min):
    last = parse_iso(item.get("lastTry"))
    return last is not None and minutes_between(now, last) < gap_min


def proxy_url(url):
    """Restituisce l'URL del proxy Cloudflare per un dato URL di YouTube."""
    if not url:
        return url
    return f"{WORKER_URL}?url={quote(url, safe='')}"


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
    if item.get("type") != "hls" or not item.get("videoId"):
        return False
    updated = parse_iso(item.get("linkUpdated"))
    if updated is None:
        return True
    if minutes_between(now, updated) >= REFRESH_HOURS * 60:
        return True
    # L'expire è dentro l'URL originale di YouTube, non in quella del proxy.
    # Lo teniamo per sicurezza se presente anche nell'URL proxato (non lo sarà di solito).
    exp = expire_of(item.get("url", ""))
    if exp and (exp - now.timestamp()) / 60 < EXPIRE_MARGIN_MIN:
        return True
    return False


def due_task(film, item, now):
    sched = last_occurrence(film["day"], film["time"], now)
    wk = sched.isoformat()
    since = minutes_between(now, sched)
    found = item.get("week") == wk

    if found:
        return None

    window = film.get("window", 120)
    if since <= window:
        return "search"

    if film.get("window") == 10 and RECHECK_UPLOAD_MIN <= since <= RECHECK_UPLOAD_MIN + 10:
        if item.get("recheck") != wk:
            return "search"

    if since <= CATCHUP_MAX_MIN and not throttled(item, now, RETRY_MIN):
        return "search"

    return None


# --------------------------------------------------------------------- YouTube
def base_opts():
    """Client ios+mweb+tv: ios funziona per m3u8, mweb/tv evitano 403 di web_safari."""
    return {
        "format": "best",
        "simulate": True,
        "quiet": True,
        "noprogress": True,
        "no_warnings": True,
        "cookiefile": "cookies.txt",
        "js_runtimes": {"node": {}},
        "extractor_args": {
            "youtube": {
                "player_client": ["ios", "mweb", "tv"],
                "player_skip": ["webpage", "configs"],
            }
        },
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


def pick_stream(info):
    formats = info.get("formats") or []

    # Seleziona solo formati HLS nativi con altezza <= 1080p
    hls_candidates = [
        f for f in formats
        if f.get("protocol") in ("m3u8_native", "m3u8")
        and f.get("height") is not None
        and f.get("height") <= 1080
        and f.get("url")
    ]

    if hls_candidates:
        # Ordina per altezza decrescente: prendi il 1080p (o il più alto sotto)
        hls_candidates.sort(key=lambda f: f["height"], reverse=True)
        best = hls_candidates[0]
        print(f"  HLS selezionato: {best.get('height')}p ({best.get('format_id')})")
        return best["url"]

    # Fallback: cerca un manifest generico (comportamento precedente)
    if info.get("manifest_url"):
        return info["manifest_url"]

    # Fallback estremo: MP4 progressivo
    muxed = [
        f for f in formats
        if str(f.get("protocol", "")).startswith(("http", "https"))
        and ".m3u8" not in (f.get("url") or "")
        and f.get("vcodec") not in (None, "none")
        and f.get("acodec") not in (None, "none")
    ]
    if muxed:
        muxed.sort(key=lambda f: f.get("height") or 0, reverse=True)
        return muxed[0]["url"]

    return info.get("url")

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
    """
    Cerca il video della settimana sia in /videos che in /streams.
    Per le premiere il video sta in /streams durante la messa in onda.
    """
    for tab in ("videos", "streams"):
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
    item["url"] = proxy_url(url)
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

    # task == "search"
    item["lastTry"] = iso(now)
    if FORCE:
        min_ts = (now - timedelta(days=30)).timestamp()
    else:
        min_ts = (sched - timedelta(hours=3)).timestamp()

    info, url = search_video(film, min_ts)
    if not info:
        print("  nessun video nuovo trovato")
        if minutes_between(now, sched) >= RECHECK_UPLOAD_MIN:
            item["recheck"] = wk
        return

    set_link(item, info, url, now)
    item["week"] = wk
    if minutes_between(now, sched) >= RECHECK_UPLOAD_MIN:
        item["recheck"] = wk
    print(f"  video trovato: {info.get('title')} ({item['state']}, {MAX_HEIGHT}p max)")


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
