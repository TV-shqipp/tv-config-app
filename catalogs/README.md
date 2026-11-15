# Kafeneja Jonë: censimento degli episodi

Rilevazione del 15 novembre 2026. Non sono stati scaricati video o file MP4.

## Risultato

| Raccolta | Voci previste | Con una fonte individuata | Non trovate |
| --- | ---: | ---: | ---: |
| Serie originale | 336 | 267 | 69 |
| Ritorno 2016 | 12 | 12 | 0 |
| Ritorno 2017 | 12 | 12 | 0 |
| Speciale Gëzuar 2020 | 1 | 1 | 0 |
| Totale | 361 | 292 | 69 |

Le 292 fonti principali comprendono 240 caricamenti ufficiali e 52 caricamenti di terzi. Per 216 puntate YouTube sono stati letti titolo, autore/canale, durata e stato della pagina video. Altre 63 sono state individuate negli elenchi pubblici ma il controllo della pagina video non si è concluso a causa dei limiti di YouTube. Le altre 13 fonti principali sono le dodici puntate 2017 del catalogo ufficiale Gjirafa e la pagina ufficiale dello speciale. Per il 2016 sono presenti anche le dodici fonti alternative Gjirafa.

Una fonte trovata non equivale a una verifica audiovisiva di ogni scena. I dati conservano queste distinzioni, le alternative, le correzioni di numerazione indicate dal canale e gli episodi non trovati. Il censimento non dimostra che i 69 mancanti siano irrecuperabili altrove.

## File

- `kafeneja-jone.html`: catalogo consultabile senza server, con filtro per raccolta, intervalli di 50 episodi, numero esatto, disponibilità e provenienza.
- `kafeneja-jone.audit.json`: dati del censimento, fonti principali e alternative, livelli di verifica, elenco dei mancanti.
- `kafeneja-jone.json`: sezione compatibile con la nuova build dell'app.
- `research/`: inventari e verifiche di lavoro. Questi file grezzi non vengono pubblicati nel repository di configurazione.

## Fonti e numerazione

- [Canale ufficiale CMB](https://www.youtube.com/c/kafenejajone/videos): inventario completo di 310 video e nove playlist; esclusi altri programmi, promo, spezzoni ed errori sul set.
- [Playlist RTK](https://www.youtube.com/playlist?list=PL2ygqgSFvmrrfmvJJQAxx1JGomNjm0QoZ) e ricerca nel canale ufficiale RTK.
- [Playlist CMB HD](https://www.youtube.com/playlist?list=PLmVY1ki89cL9YR6jSUQpkPHYAduX6ilWn) e [playlist CMB 2016](https://www.youtube.com/playlist?list=PLmVY1ki89cL_m5S1Bcrv5fu0tlqFu-opM).
- Due ricerche individuali per i numeri non presenti nel primo inventario, più una playlist storica usata come ulteriore indice. I caricamenti di terzi non vengono presentati come ufficiali.
- [Gjirafa 2016](https://video.gjirafa.com/kafenejajone2016): dodici puntate nel catalogo pubblico della stagione `2B0jBaL6mY`.
- [Gjirafa 2017](https://video.gjirafa.com/kafenejajone): dodici puntate nella stagione `zlPj2ao6E8`.
- [Speciale Gëzuar 2020](https://video.gjirafa.com/kafeneja-jone-episodi-festiv-gezuar-2020).
- Il termine della serie originale all'episodio 336 è documentato anche [nell'annuncio del dicembre 2013](https://lajmi.net/perfundoi-kafeneja-jone/).

I ritorni ripartono da 1 nella navigazione. Nel JSON sono conservati anche i numeri cumulativi 337–348 e 349–360. Lo speciale rimane separato. Gli «Extra» del sito Gjirafa includono clip e promo e non diventano nuove puntate.

## Integrazione e verifiche

La nuova build mostra una sola sezione `Seriale Shqip`, con i cinque titoli già presenti e `Kafeneja Jonë → Krejt epizodat`, poi le quattro raccolte. Il selettore `Zgjidh grupin e episodeve` usa intervalli 1–50, 51–100, fino a 301–350 per la serie originale. `Kërko epizodin` permette di inserire il numero esatto anche quando è selezionato un altro intervallo; la scelta rimane quando si torna dal player. I mancanti sono visibili e aprono un messaggio esplicito. Conteggi del tipo trovati/totale e note di verifica rimangono nel rapporto tecnico e non sono mostrati nell'app.

Per YouTube viene conservato solo l'ID; il flusso viene risolto dal dispositivo. Per Gjirafa viene conservata solo la pagina ufficiale e letto il player pubblico del video selezionato al clic. Non vengono scelti video raccomandati; contenuti bloccati o protetti non vengono risolti. Se il parsing non riesce, viene aperta la pagina ufficiale nel player web esistente.

Il catalogo è incluso negli asset e nel config remoto. La sezione mantiene l'ID `filma-shqip` per compatibilità con gli updater e ha titolo `Seriale Shqip`. La precedente sezione separata `seriale-shqip` viene unita automaticamente, conservando i dati remoti dei cinque titoli. Il workflow e gli orari delle GitHub Actions restano invariati. I file pubblicati in `catalogs/` sono il catalogo e il rapporto del censimento, non un aggiornamento APK.

Verificati 13 test mirati, inclusi numerazione e buchi, intervalli, parsing del config e selezione del video Gjirafa corretto. La prova online ha risolto le pagine 2017 episodio 1, 2017 episodio 12 e speciale 2020 e letto con successo i rispettivi manifest HLS pubblici. Compilazione debug riuscita. Riproduzione e navigazione su TV fisica ancora da provare: nessun dispositivo ADB collegato.
