# Filma Live - integrazione nativa sperimentale

Verifica: 15 novembre 2026.

Sono stati predisposti nove canali sotto Kanale TV > Filma Live: Film Aksion, Film Komedi, Film Thriller, Film Hits, Tring Action, Tring Comedy, Tring Fantasy, Tring Classic e Tring Shqip.

## Fonte e protocollo

Il servizio utilizzato e OHA.TO, fonte di terzi, non un endpoint ufficiale DigitAlb/Tring. L'accessibilita tecnica non certifica l'autorizzazione del servizio a distribuire i programmi. Non viene incorporato VYPN e non vengono copiate identita, cookie o credenziali di quell'app.

La ricerca iniziale ha identificato il protocollo pubblico mHub v2:
- https://www.mhub.mx/mhub-api.md
- https://github.com/MediaHubMX/protocol
- https://oha.to/mhub-addon.json
- https://oha.to/live/mhub-addon.json

Il manifest Live dichiara identita opzionale. Nelle prove il catalogo e il resolver hanno risposto HTTP 200 a richieste ordinarie senza identita VYPN. L'app usa solo questi endpoint pubblici:
- catalog/live/channels.json?search=nome
- resolve?url=pagina-originale-del-canale

La risposta del resolver contiene il link HLS corrente. Il browser web puo bloccarne la riproduzione perche il contenuto e HTTP dentro una pagina HTTPS; il player nativo Android non e una pagina web. Le impostazioni esistenti dell'app gia consentivano HTTP e non sono state allentate.

## Implementazione

OhaLive.kt cerca il nome esatto del canale, ammettendo solo suffissi di qualita HD/FHD/SD e numeri di variante. Non seleziona un canale diverso se quello richiesto manca. Ogni variante deve rispondere con HLS valido prima di essere passata al player. Un esempio: Film Aksion aveva due varianti funzionanti e una variante HD con HTTP 502. La variante guasta viene ignorata.

ItemLauncher e PlayerActivity aprono il flusso con ExoPlayer, senza browser esterno o WebView. Dopo un errore di rete il player richiede nuovamente il link, con massimo tre tentativi. Per le dirette riparte al punto live; per Gjirafa resta invariato il recupero della posizione VOD. Nessuna garanzia di disponibilita permanente della fonte.

Nel config restano nome, ID, pagina originale e, quando fornita dal catalogo, icona. Nessun m3u8 con token viene salvato nel config, nei rapporti o nella cache della configurazione. Nessun file video e stato scaricato su disco. Gli script di verifica leggono solo piccoli campioni dei segmenti in memoria.

## Verifiche

- Test JVM del resolver nativo: tutti e nove i canali risolti con manifest HLS valido.
- Controllo separato: tutti e nove con accesso HTTP 200/206 a un piccolo campione di segmento video; risultati nei singoli JSON.
- Test di corrispondenza canale, rifiuto URL locali/non multimediali e credenziali negli URL.
- Test unitari del progetto e compilazione debug riusciti.
- Non e stata verificata la visione integrale o la decodifica su ogni modello di TV. Non e stata provata una scadenza reale durante una trasmissione lunga.
- Serve installare la nuova build per il tipo oha_live. Nessun APK pubblicato.

I file Kotlin modificati si trovano nel progetto Android locale: OhaLive.kt, ItemLauncher.kt, PlayerActivity.kt e ItemAdapter.kt. Il repository tv-config-app contiene configurazione e prove, non il sorgente completo dell'app Android.
