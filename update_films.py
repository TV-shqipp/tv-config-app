"""Filma Shqip: tiene aggiornati nel config.json i link dei film presi da YouTube."""

import json
import os
import re
import sys
import unicodedata
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

CONFIG_FILE = "config.json"
GROUP_ID = "filma-shqip"
TZ = ZoneInfo("Europe/Rome")
UTC = timezone.utc

# ---------------------------------------------------------------- impostazioni
REFRESH_HOURS = 5
EXPIRE_MARGIN_MIN = 90
RECHECK_UPLOAD_MIN = 90
LIVE_MIN = 120
RETRY_MIN = 15
LIVE_POLL_MIN = 3   # modalità "live": al massimo un controllo ogni 3 minuti (meno chiamate a YouTube e meno commit)
CATCHUP_MIN = 60
CATCHUP_MAX_MIN = 72 * 60

OFFLINE_MESSAGE = "Il film di questa settimana non è ancora disponibile.\nRiprova più tardi."

FILMS = [
    {
        "id": "edhe-malet-flasin",
        "name": "Edhe malet flasin",
        "channel": "@EdaFilms2",
        "mode": "upload",
        "day": 5,
        "time": "20:31",
        "window": 10,
        "keywords": ["edhe malet flasin"],
        "exclude": ["promo"],
    },
    {
        "id": "rrugt-e-lirise",
        "name": "Rrugët e Lirisë",
        "channel": "@ProduksioniDONJETA",
        "mode": "upload",
        "day": 4,
        "time": "20:00",
        "window": 10,
        "keywords": ["rrugët e lirisë"],
        "exclude": ["promo"],
    },
    {
        "id": "bashkallajk",
        "name": "Bashkallajk",
        "channel": "@teve1",
        "mode": "live",
        "day": 4,
        "time": "20:45",
        "keywords": ["bashkallajk"],
        "exclude": ["promo"],
    },
    {
        "id": "nusja-me-shkolle",
        "name": "Nusja me shkollë",
        "channel": "@DTVOff",
        "mode": "live",
        "day": 5,
        "time": "20:30",
        "keywords": ["nusja me shkollë"],
        "exclude": ["promo"],
    },
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
        group = {
            "id": GROUP_ID, "title": "Filma Shqip", "subtitle": "Filme shqiptare",
            "icon": "", "type": "group", "items": [],
        }
        items.append(group)
        changed = True
    sub = group.setdefault("items", [])
    for film in FILMS:
        if not any(i.get("id") == film["id"] for i in sub):
            sub.append({
                "id": film["id"], "name": film["name"], "icon": "",
                "type": "offline", "message": OFFLINE_MESSAGE,
            })
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
    if updated is None: return True
    if minutes_between(now, updated) >= REFRESH_HOURS * 60: return True
    exp = expire_of(item.get("url", ""))
    if exp and (exp - now.timestamp()) / 60 < EXPIRE_MARGIN_MIN: return True
    return False

def due_task(film, item, now):
    sched = last_occurrence(film["day"], film["time"], now)
    wk = sched.isoformat()
    since = minutes_between(now, sched)
    found = item.get("week") == wk

    if film["mode"] == "upload":
        if since <= film["window"] and not found: return "search"
        if (RECHECK_UPLOAD_MIN <= since <= 240 and item.get("recheck") != wk
                and not throttled(item, now, RETRY_MIN)): return "search"
        if (not found and (since <= CATCHUP_MAX_MIN or item.get("type") == "offline")
                and not throttled(item, now, CATCHUP_MIN)): return "search"
    else:
        is_current_live = found and item.get("state") == "live"
        if not is_current_live:
            if since < LIVE_MIN:
                return None if throttled(item, now, LIVE_POLL_MIN) else "live"
            live_since = since
        else:
            started = parse_iso(item.get("liveStartedAt")) or sched
            live_since = minutes_between(now, started)
            if live_since < LIVE_MIN: return None
        
        if ((LIVE_MIN <= live_since <= CATCHUP_MAX_MIN or item.get("type") == "offline") 
                and item.get("recheck") != wk
                and not throttled(item, now, RETRY_MIN)): return "search"
    return None

# --------------------------------------------------------------------- YouTube
def base_opts():
    return {
        "format": "best", "simulate": True, "quiet": True, "cookiefile": "cookies.txt",
        "js_runtimes": {"node": {}}, "extractor_args": {"youtube": {"player_client": ["web_safari", "web"]}},
    }

def extract(url):
    import yt_dlp
    opts = base_opts()
    opts["ignore_no_formats_error"] = True
    with yt_dlp.YoutubeDL(opts) as ydl:
        return ydl.extract_info(url, download=False)

def list_channel(film, tab=None):
    import yt_dlp
    if tab is None:
        tab = "videos" if film["mode"] == "upload" else "streams"
    url = f"https://www.youtube.com/{film['channel']}/{tab}"
    opts = base_opts()
    # AUMENTATO A 50: così trova i video anche se ci sono molte news nel canale
    opts.update({"extract_flat": "in_playlist", "playlistend": 50})
    with yt_dlp.YoutubeDL(opts) as ydl:
        info = ydl.extract_info(url, download=False)
    return [e for e in ((info or {}).get("entries") or []) if e and e.get("id")]

def pick_m3u8(info):
    for fmt in reversed(info.get("formats") or []):
        url = fmt.get("url") or ""
        protocol = str(fmt.get("protocol") or "")
        if ".m3u8" in url or protocol.startswith("m3u8"): return url
    return info.get("manifest_url") or info.get("url")

def video_ts(info):
    ts = info.get("release_timestamp") or info.get("timestamp")
    if ts: return ts
    date = info.get("upload_date")
    if date:
        try:
            day = datetime.strptime(date, "%Y%m%d").replace(tzinfo=TZ)
            return (day + timedelta(days=1)).timestamp() - 1
        except ValueError: pass
    return None

def search_video(film, min_ts, tab=None):
    tabs = ["videos", "streams"] if film["mode"] == "live" and tab is None else [tab] if tab else ["videos"]
    for current_tab in tabs:
        try:
            entries = list_channel(film, current_tab)
        except Exception as e:
            print(f"  errore lettura tab {current_tab}: {e}")
            continue
            
        for entry in entries:
            if not title_ok(entry.get("title"), film): continue
            if entry.get("live_status") == "is_upcoming":
                print(f"  premiere programmata: {entry.get('title')} (salto per cercare video vecchi)")
                continue
                
            try:
                info = extract(f"https://www.youtube.com/watch?v={entry['id']}")
            except Exception as e:
                print(f"  errore estrazione: {e}")
                continue
                
            if info.get("live_status") == "is_upcoming": continue
            ts = video_ts(info)
            m3u8 = pick_m3u8(info)
            
            if not m3u8:
                print("  video trovato ma senza flusso m3u8")
                continue
            
            is_this_week = True
            if ts is not None and ts < min_ts:
                is_this_week = False
                print(f"  trovato video vecchio: {info.get('title')}")
            else:
                print(f"  trovato video recente: {info.get('title')}")
                
            return info, m3u8, is_this_week
    return None, None, False

def set_link(item, info, m3u8, now):
    item["type"] = "hls"
    item["url"] = m3u8
    item["videoId"] = info.get("id")
    item["videoTitle"] = info.get("title")
    live = info.get("live_status") == "is_live" or info.get("is_live")
    item["state"] = "live" if live else "vod"
    item["linkUpdated"] = iso(now)
    if live:
        started = info.get("release_timestamp") or info.get("timestamp")
        if started: item["liveStartedAt"] = iso(datetime.fromtimestamp(started, UTC))
        elif not item.get("liveStartedAt"): item["liveStartedAt"] = iso(now)
    else:
        item.pop("liveStartedAt", None)
    item.pop("message", None)
    item.pop("pageUrl", None)

def do_refresh(item, now):
    info = extract(f"https://www.youtube.com/watch?v={item['videoId']}")
    m3u8 = pick_m3u8(info)
    if not m3u8:
        print("  rinnovo fallito: nessun flusso m3u8, tengo il link vecchio")
        return
    set_link(item, info, m3u8, now)
    print("  link rinnovato")

def run_task(film, item, task, now):
    sched = last_occurrence(film["day"], film["time"], now)
    wk = sched.isoformat()
    since = minutes_between(now, sched)

    if task == "refresh":
        do_refresh(item, now)
        return

    if task == "live":
        try:
            info = extract(f"https://www.youtube.com/{film['channel']}/live")
            title = info.get("title")
            if (info.get("is_live") or info.get("live_status") == "is_live") and title_ok(title, film):
                m3u8 = pick_m3u8(info)
                if not m3u8:
                    print("  in diretta ma senza flusso m3u8")
                    item["lastTry"] = iso(now)  # registra il tentativo, altrimenti il controllo riparte a ogni minuto
                    return
                set_link(item, info, m3u8, now)
                item["week"] = wk
                print(f"  diretta trovata: {title}")
                return
            if title:
                print(f"  in diretta ma con un altro titolo: {title}")
        except Exception as e:
            # FIX: Non facciamo crashare tutto se /live dà errore, passiamo ai video normali
            print(f"  errore su /live: {e}. Passo alla ricerca nel canale...")

        print("  cerco la premiere/video nel canale...")
        item["lastTry"] = iso(now)
        fallback_min_ts = sched.timestamp()
        
        result_info, result_m3u8, is_this_week = search_video(film, fallback_min_ts)
        
        if result_info and result_m3u8:
            set_link(item, result_info, result_m3u8, now)
            if is_this_week: item["week"] = wk
            print(f"  video/premiere trovato: {result_info.get('title')}")
        return

    # task == "search"
    item["lastTry"] = iso(now)
    if FORCE:
        min_ts = (now - timedelta(days=30)).timestamp() 
    else:
        min_ts = (sched - timedelta(hours=3)).timestamp()
        
    result_info, result_m3u8, is_this_week = search_video(film, min_ts)
    
    if not result_info:
        print("  nessun video trovato")
        return
        
    set_link(item, result_info, result_m3u8, now)
    if is_this_week:
        item["week"] = wk
        if since >= (RECHECK_UPLOAD_MIN if film["mode"] == "upload" else LIVE_MIN):
            item["recheck"] = wk
    print(f"  video trovato: {result_info.get('title')}")

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
        if item is None: continue
        task = "search" if FORCE else due_task(film, item, now)
        if task is None and refresh_needed(item, now): task = "refresh"
        if task: work.append((film, item, task))

    print(f"Ora italiana: {now:%Y-%m-%d %H:%M}")
    for film, _, task in work:
        print(f"- {film['name']}: {task}")
    run = bool(work) or changed

    if PLAN:
        if not run: print("Niente da fare.")
        write_output(run)
        return

    if not run:
        print("Niente da fare.")
        return

    for film, item, task in work:
        print(f"[{film['name']}] {task}")
        before = json.dumps(item, sort_keys=True)
        try:
            run_task(film, item, task, now)
        except Exception as e:
            print(f"  errore: {e}")
        if task != "refresh" and refresh_needed(item, now):
            try:
                do_refresh(item, now)
            except Exception as e:
                print(f"  errore nel rinnovo: {e}")
        if json.dumps(item, sort_keys=True) != before:
            changed = True

    if changed:
        save_config(data)
        print("config.json aggiornato.")
    else:
        print("Nessuna modifica necessaria.")

if __name__ == "__main__":
    main()
