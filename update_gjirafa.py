#!/usr/bin/env python3
"""
Aggiorna in config.json i link .m3u8 dei canali GjirafaVideo.

Differenze rispetto alla vecchia versione:
  - raccoglie TUTTI i .m3u8 visti dalla pagina (non solo il primo)
  - scarta quelli che sembrano pubblicita' (VAST, doubleclick, ...)
  - verifica ogni candidato scaricandolo: deve rispondere 200, essere una playlist
    HLS valida e NON essere un video registrato (#EXT-X-ENDLIST = spot/VOD)
  - preferisce la master playlist (tutte le qualita')
  - se non trova nulla di valido NON tocca il link che c'era
  - non cambia mai il "type" del canale (la radio resta "audio")
"""
import asyncio
import json
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urljoin

import requests
from playwright.async_api import async_playwright

CONFIG_PATH = Path(__file__).resolve().parent / "config.json"

# id del canale nel config.json -> pagina GjirafaVideo (da verificare nel browser!)
PAGES = {
    "radio-dukagjini": "https://video.gjirafa.com/radio-dukagjini",
    "rtv-21": "https://video.gjirafa.com/rtv-21-live",
    "ktv": "https://video.gjirafa.com/ktv-live",
    "atv": "https://video.gjirafa.com/atv-live-tv",
}

UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
)
REFERER = "https://video.gjirafa.com/"

AD_WORDS = (
    "doubleclick", "googlesyndication", "googleads", "adserver", "imasdk",
    "preroll", "/vast", "vast.", "adsystem",
)

# Prova a far partire il video (molti player aspettano un click)
PLAY_JS = """() => {
  try {
    const v = document.querySelector('video');
    if (v) { v.muted = true; v.play(); }
    const sels = ['.vjs-big-play-button', '.jw-icon-display', '.plyr__control--overlaid',
                  '.ytp-large-play-button', 'button[aria-label*="lay"]',
                  '[class*="play-button"]', '[class*="playButton"]'];
    for (const s of sels) { const el = document.querySelector(s); if (el) { el.click(); break; } }
  } catch (e) {}
}"""


def is_ad(url: str) -> bool:
    u = url.lower()
    return any(w in u for w in AD_WORDS)


def fetch(url: str, referer: str = REFERER):
    try:
        r = requests.get(url, headers={"User-Agent": UA, "Referer": referer}, timeout=15)
        return r.status_code, r.text
    except requests.RequestException as e:
        return 0, str(e)


def inspect(url: str, referer: str = REFERER):
    """Ritorna (ok, is_live, is_master, nota)."""
    status, text = fetch(url, referer)
    if status != 200 or not text.lstrip().startswith("#EXTM3U"):
        return False, False, False, f"HTTP {status}" if status else f"errore: {text[:60]}"

    is_master = "#EXT-X-STREAM-INF" in text
    live = "#EXT-X-ENDLIST" not in text

    if is_master:
        variant = next(
            (l.strip() for l in text.splitlines() if l.strip() and not l.startswith("#")), None
        )
        if variant:
            vs, vt = fetch(urljoin(url, variant), referer)
            if vs != 200 or not vt.lstrip().startswith("#EXTM3U"):
                return False, False, True, f"variante HTTP {vs}"
            live = "#EXT-X-ENDLIST" not in vt
    return True, live, is_master, "ok"


def pick_best(candidates, referer: str = REFERER):
    good = []
    for url in candidates:
        if is_ad(url):
            print(f"  [scartato: pubblicita'] {url}")
            continue
        ok, live, master, note = inspect(url, referer)
        tipo = "master" if master else "media"
        stato = "LIVE" if live else "NON-live (VOD/spot)"
        print(f"  [{note}] [{tipo}] [{stato}] {url}")
        if ok and live:
            good.append((0 if master else 1, url))
    if not good:
        return None
    good.sort(key=lambda t: t[0])  # sort stabile: master prima, poi ordine di apparizione
    return good[0][1]


async def collect(browser, page_url: str, wait_ms: int = 12000):
    """Apre la pagina e restituisce tutti gli URL .m3u8 richiesti, in ordine."""
    seen = []
    context = await browser.new_context(user_agent=UA, viewport={"width": 1280, "height": 720})
    page = await context.new_page()

    def on_request(req):
        u = req.url
        if ".m3u8" in u.split("?")[0] and u not in seen:
            seen.append(u)

    page.on("request", on_request)
    try:
        await page.goto(page_url, wait_until="domcontentloaded", timeout=45000)
    except Exception as e:  # noqa: BLE001
        print(f"  attenzione caricamento pagina: {e}")
    await page.wait_for_timeout(3000)
    for frame in page.frames:  # il player e' spesso dentro un iframe
        try:
            await frame.evaluate(PLAY_JS)
        except Exception:  # noqa: BLE001
            pass
    await page.wait_for_timeout(wait_ms)
    await context.close()
    return seen


async def main():
    config = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    items = {
        it["id"]: it
        for section in config.get("sections", [])
        for it in section.get("items", [])
        if "id" in it
    }

    changed = False
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        for cid, page_url in PAGES.items():
            item = items.get(cid)
            if item is None:
                print(f"::warning::{cid}: non presente nel config.json, salto")
                continue

            print(f"\n=== {cid}  ({page_url}) ===")
            candidates = await collect(browser, page_url)
            print(f"  trovati {len(candidates)} link .m3u8")
            new_url = pick_best(candidates)

            if not new_url:
                print(f"::warning::{cid}: nessun link valido, mantengo quello precedente")
                continue
            if item.get("url") != new_url:
                item["url"] = new_url
                changed = True
                print("  -> AGGIORNATO")
            else:
                print("  -> invariato")
        await browser.close()

    if changed:
        config["updated"] = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        CONFIG_PATH.write_text(
            json.dumps(config, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
        )
        print("\nconfig.json aggiornato")
    else:
        print("\nNessuna modifica")


if __name__ == "__main__":
    asyncio.run(main())
