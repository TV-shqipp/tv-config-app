#!/usr/bin/env python3
"""
Prova qualsiasi pagina di streaming (es. Klan Kosova) dal tuo PC:
mostra tutti i link .m3u8 che la pagina richiede e dice se funzionano.

Uso:
    pip install playwright requests
    playwright install chromium
    python test_stream.py https://stream.klankosova.tv/
    python test_stream.py https://stream.klankosova.tv/ --show --wait 20

  --show   apre la finestra del browser (utile per cliccare play a mano)
  --wait   secondi di attesa dopo il caricamento (default 15)
"""
import argparse
import asyncio

from playwright.async_api import async_playwright

from update_gjirafa import UA, collect, inspect, is_ad


async def run(url: str, show: bool, wait: int):
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=not show)
        print(f"Apro {url} e aspetto {wait}s ...")
        seen = await collect(browser, url, wait_ms=wait * 1000)
        await browser.close()

    print(f"\nLink .m3u8 trovati: {len(seen)}\n")
    if not seen:
        print("Nessun link. Prova con --show e clicca play a mano: se anche cosi' non")
        print("compare nulla, il sito usa un altro sistema (DASH, DRM, iframe protetto).")
        return

    best = None
    for u in seen:
        if is_ad(u):
            print(f"[PUBBLICITA']  {u}\n")
            continue
        ok, live, master, note = inspect(u, referer=url)
        print(f"[{'OK' if ok else 'ERRORE: ' + note}] "
              f"[{'master' if master else 'media'}] "
              f"[{'LIVE' if live else 'NON live'}]\n  {u}\n")
        if ok and live and best is None:
            best = u

    if best:
        print("Link consigliato (provalo anche in VLC: Media > Apri flusso di rete):")
        print(best)
        print(f"\nIn VLC/app servono questi header -> Referer: {url}   User-Agent: {UA}")
    else:
        print("Nessun link utilizzabile.")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("url")
    ap.add_argument("--show", action="store_true")
    ap.add_argument("--wait", type=int, default=15)
    args = ap.parse_args()
    asyncio.run(run(args.url, args.show, args.wait))
