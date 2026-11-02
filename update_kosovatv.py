#!/usr/bin/env python3
"""Aggiorna solo gli 11 canali KosovaTV richiesti nel config dell'app.

Python 3.12+, curl e ffprobe. Nessun pacchetto pip, account o cookie.
"""

import argparse
import copy
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
import unicodedata
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlencode, urljoin, urlparse

BASE = "https://kosovatv.live/"
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/131.0.0.0 Safari/537.36"
ICON_BASE = "https://raw.githubusercontent.com/TV-shqipp/tv-config-app/main/icon/"
# key, nome, alias sul sito, ID locali, contenitore, icona di riserva
TARGETS = [
    ("rtk1", "RTK 1", ("rtk1",), ("rtk1",), "rtk-group", "rtk-1.png"),
    ("rtk2", "RTK 2", ("rtk2",), ("rtk2",), "rtk-group", "rtk-2.png"),
    ("rtk3", "RTK 3", ("rtk3",), ("rtk3",), "rtk-group", "rtk-3.png"),
    ("rtk4", "RTK 4", ("rtk4",), ("rtk4",), "rtk-group", "rtk-4.png"),
    ("dukagjini", "TV Dukagjini", ("dukagjini", "tvdukagjini"), ("tv-dukagjini",), "tv", "dukagjini.jpg"),
    ("teve1", "Tëvë 1", ("teve1",), ("teve1", "teve-1", "teve"), "tv", ""),
    ("top-channel", "Top Channel", ("topchannel",), ("top-channel",), "tv", ""),
    ("klan-tv", "Klan TV", ("klantv",), ("klan-tv",), "tv", ""),
    ("klan-plus", "Klan Plus", ("klanplus",), ("klan-plus",), "tv", ""),
    ("bbvk1", "BB VIP Kosova 1", ("bbvipkosova1",), ("bbvk-kanali-1", "bbvk-kanali-1-hd"), "bbvk-group", "bbvk1.png"),
    ("bbvk2", "BB VIP Kosova 2", ("bbvipkosova2",), ("bbvk-kanali-2", "bbvk-kanali-2-hd"), "bbvk-group", "bbvk2.png"),
]


def now():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def normalize(value):
    text = unicodedata.normalize("NFKD", str(value)).encode("ascii", "ignore").decode().lower()
    text = re.sub(r"[^a-z0-9]", "", text)
    return re.sub(r"(?:uhd|fhd|hd|4k|sd)+$", "", text)


def fetch(url):
    """Usa curl (urllib riceve 403 da questo sito), verificando TLS normalmente."""
    result = subprocess.run(
        ["curl", "--silent", "--show-error", "--location", "--fail",
         "--proto", "=https,http", "--proto-redir", "=https,http",
         "--connect-timeout", "8", "--max-time", "25", "--max-filesize", "16777216",
         "--user-agent", UA, "--referer", BASE,
         "--write-out", "\n__KTV_URL__%{url_effective}", url],
        capture_output=True, timeout=30,
    )
    if result.returncode:
        # Non stampare URL upstream che potrebbero contenere credenziali.
        status = re.search(rb"error: (\d{3})", result.stderr)
        raise RuntimeError("HTTP " + status[1].decode() if status else f"curl errore {result.returncode}")
    body, effective = result.stdout.rsplit(b"\n__KTV_URL__", 1)
    return body, effective.decode()


def fetch_json(url):
    return json.loads(fetch(url)[0])


def discover_relays():
    """Rilegge lo script player attuale: niente versione speciale BBVK fissa."""
    html = fetch(BASE)[0].decode("utf-8", "replace")
    scripts = re.findall(r'<script\b[^>]*\bsrc=[\'"]([^\'"]+)', html, re.I)
    player = next((urljoin(BASE, s) for s in scripts
                   if re.search(r"/assets/js/player[^/]*\.js(?:\?|$)", s)), None)
    if not player or urlparse(player).netloc != urlparse(BASE).netloc:
        raise RuntimeError("Script player non riconosciuto: controllare il sito")
    js = fetch(player)[0].decode("utf-8", "replace")
    paths = list(dict.fromkeys(re.findall(r"/api/hls[A-Za-z0-9_\-]*\.php", js)))
    if "/api/hls.php" not in paths:
        raise RuntimeError("Endpoint HLS standard non trovato nel player")
    special = [p for p in paths if "special" in p]
    return "/api/hls.php", special


def validate_hls(url, depth=0):
    if depth > 3:
        raise RuntimeError("Troppe playlist annidate")
    body, effective = fetch(url)
    text = body.decode("utf-8-sig", "replace").strip()
    if not text.startswith("#EXTM3U"):
        raise RuntimeError("La risposta non è una playlist HLS")
    lines = [s.strip() for s in text.splitlines() if s.strip()]
    # Un master non si può dare per valido senza verificare una variante.
    variants = [lines[i + 1] for i, s in enumerate(lines[:-1])
                if s.startswith("#EXT-X-STREAM-INF:") and not lines[i + 1].startswith("#")]
    if variants:
        return validate_hls(urljoin(effective, variants[0]), depth + 1)
    segments = [s for s in lines if not s.startswith("#")]
    if not segments or "#EXTINF:" not in text:
        raise RuntimeError("Playlist senza segmenti video")
    # Un segmento arretrato è meno esposto alla corsa tra creazione e lettura.
    data = fetch(urljoin(effective, segments[max(0, len(segments) - 2)]))[0]
    probe = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries",
         "stream=codec_name,codec_type,width,height", "-of", "json", "-i", "pipe:0"],
        input=data, capture_output=True, timeout=20,
    )
    streams = json.loads(probe.stdout).get("streams", [])
    if probe.returncode or not any(s.get("codec_type") == "video" for s in streams):
        raise RuntimeError("Segmento senza traccia video riconoscibile da ffprobe")
    return streams


def resolve():
    for executable in ("curl", "ffprobe"):
        if not shutil.which(executable):
            raise RuntimeError(f"Programma richiesto non installato: {executable}")
    catalogue = fetch_json(urljoin(BASE, "api/channels.php"))
    if catalogue.get("ok") is not True or not isinstance(catalogue.get("channels"), list):
        raise RuntimeError("Elenco canali non valido")
    standard, special = discover_relays()
    report = {"checkedAt": now(), "results": {}}
    for key, name, aliases, *_ in TARGETS:
        matches = [c for c in catalogue["channels"] if normalize(c.get("name", "")) in aliases]
        # Preferenza HD; la variante 4K, se presente, resta un'alternativa verificata.
        matches.sort(key=lambda c: "4k" in unicodedata.normalize("NFKD", c.get("name", "")).lower())
        errors = []
        found = None
        for channel in matches:
            if channel.get("locked") or channel.get("can_play") is False or channel.get("access_level") != "free":
                errors.append("Canale non accessibile senza abbonamento")
                continue
            try:
                cid = int(channel["id"])
                play = fetch_json(urljoin(BASE, f"api/play.php?id={cid}"))
                if play.get("ok") is not True or not isinstance(play.get("sources"), list):
                    raise RuntimeError("API play non disponibile")
                relays = special + [standard] if key.startswith("bbvk") else [standard]
                for relay in relays:
                    for source in range(1, len(play["sources"]) + 1):
                        url = urljoin(BASE, relay) + "?" + urlencode({"id": cid, "source": source})
                        # Un 503 può indicare che il relay sta ancora preparando il flusso.
                        for attempt in range(2):
                            try:
                                streams = validate_hls(url)
                                found = {"url": url, "logo": channel.get("logo", ""), "streams": streams}
                                break
                            except (RuntimeError, ValueError, subprocess.SubprocessError) as exc:
                                if attempt == 0:
                                    time.sleep(2)
                                else:
                                    errors.append(str(exc))
                        if found:
                            break
                    if found:
                        break
            except (RuntimeError, ValueError, KeyError, subprocess.SubprocessError) as exc:
                errors.append(str(exc))
            if found:
                break
        report["results"][key] = found or {"error": "; ".join(dict.fromkeys(errors)) or "Canale non trovato"}
        print(f"{name}: {'OK' if found else 'ERRORE - conservato il valore precedente'}", flush=True)
    return report


def walk(nodes):
    for node in nodes:
        yield node
        yield from walk(node.get("items", []))


def merge(config, report):
    """Applica solo gli esiti validi; mantiene gruppi, ID, icone ed altri contenuti."""
    out = copy.deepcopy(config)
    if not isinstance(out.get("sections"), list):
        raise ValueError("config.json deve contenere sections[]")
    nodes = list(walk(out["sections"]))
    tv = next((n for n in out["sections"] if n.get("id") == "tv"), None)
    if tv is None or not isinstance(tv.get("items"), list):
        raise ValueError("Sezione tv con items[] non trovata")
    results = report.get("results", {})
    for key, name, _, ids, parent_id, icon in TARGETS:
        result = results.get(key, {})
        if not result.get("url") or result.get("error"):
            continue
        url = result["url"]
        parsed = urlparse(url)
        if parsed.scheme != "https" or parsed.netloc != "kosovatv.live" or not parsed.path.startswith("/api/hls"):
            raise ValueError(f"URL relay non valido per {key}")
        items = [n for n in nodes if n.get("id") in ids]
        if not items:
            parent = next((n for n in nodes if n.get("id") == parent_id), None)
            if parent is None:
                if parent_id == "rtk-group":
                    parent = {"id": parent_id, "title": "Rtk-Group", "type": "group", "items": []}
                    tv["items"].append(parent)
                else:
                    parent = {"id": parent_id, "title": "Big Brother VIP Kosova", "items": []}
                    out["sections"].append(parent)
                nodes.append(parent)
            item = {"id": ids[0], "name": name,
                    "icon": ICON_BASE + icon if icon else result.get("logo", "")}
            parent.setdefault("items", []).append(item)
            nodes.append(item)
            items = [item]
        for item in items:
            # Elimina i vecchi percorsi WebView/YouTube, che altrimenti possono
            # avere precedenza sul nuovo url HLS nell'app.
            for field in ("pageUrl", "forceWeb", "externalBrowser", "videoId", "liveVideoId", "userAgent"):
                item.pop(field, None)
            item.update(type="hls", url=url, referer=BASE, userAgent=UA)
    if out != config:
        version = config.get("version", 0)
        if type(version) is not int:
            raise ValueError("version deve essere un intero")
        out["version"] = version + 1
        out["updated"] = now()
    return out


def write_json(path, data):
    """Sostituzione atomica: un'interruzione non lascia un config parziale."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = None
    try:
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", newline="\n",
                                         dir=path.parent, delete=False) as f:
            tmp = Path(f.name)
            json.dump(data, f, indent=2, ensure_ascii=False)
            f.write("\n")
        os.replace(tmp, path)
    finally:
        if tmp is not None and tmp.exists():
            tmp.unlink()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--resolve", type=Path, help="Verifica il sito e salva un report, senza toccare config.json")
    mode.add_argument("--apply", type=Path, help="Applica un report già verificato al config più recente")
    parser.add_argument("--config", type=Path, default=Path("config.json"))
    parser.add_argument("--dry-run", action="store_true", help="Non scrivere config.json")
    args = parser.parse_args()
    if args.apply:
        report = json.loads(args.apply.read_text(encoding="utf-8"))
    else:
        report = resolve()
        write_json(args.resolve or Path("kosovatv-report.json"), report)
        summary = os.environ.get("GITHUB_STEP_SUMMARY")
        if summary:
            with open(summary, "a", encoding="utf-8") as f:
                f.write("### Verifica KosovaTV\n\n| Canale | Esito |\n|---|---|\n")
                for key, name, *_ in TARGETS:
                    ok = "url" in report["results"][key]
                    f.write(f"| {name} | {'OK' if ok else 'Errore: mantenuto il valore precedente'} |\n")
    if args.resolve:
        return 0
    config = json.loads(args.config.read_text(encoding="utf-8-sig"))
    updated = merge(config, report)
    if updated == config:
        print("Nessuna modifica al config")
    elif args.dry_run:
        print(f"DRY RUN: verrebbe aggiornata la versione a {updated['version']}")
    else:
        write_json(args.config, updated)
        print(f"Config aggiornato, versione {updated['version']}")
    # Le modifiche valide sono salvate anche in caso di errori parziali.
    return 1 if any("url" not in report.get("results", {}).get(t[0], {}) for t in TARGETS) else 0


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    try:
        sys.exit(main())
    except (RuntimeError, ValueError, OSError, subprocess.SubprocessError) as exc:
        print(f"Errore: {exc}", file=sys.stderr)
        sys.exit(2)
