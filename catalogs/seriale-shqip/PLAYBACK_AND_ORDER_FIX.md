# Correzione Gjirafa e ordinamento delle raccolte

Verifica del 15 novembre 2026.

## Gjirafa

Il manifest statico di Rrushe episodio 1, presente in `playerConfig.dvrPlaybackUrls`, restituisce HTTP 403. La pagina originale fornisce anche `geoBlockConfig.secureLink`: chiamando questo endpoint ufficiale si ottiene un nuovo manifest firmato. Manifest principale e playlist video firmati rispondono HTTP 200.

`GjirafaEpisode.resolve` ora legge l'endpoint dell'episodio selezionato, richiede il link corrente all'API ufficiale e passa direttamente il relativo m3u8 al player nativo. Per gli episodi senza endpoint di firma rimane il manifest pubblico della pagina originale. Non vengono salvati token, manifest firmati o file video nel catalogo. Gli URL firmati scadono: nel campione controllato la validita residua era circa 40 minuti. Il player rinnova il link dopo un errore di rete, conserva la posizione e lo stato play/pausa, con massimo tre tentativi nella sessione. I controlli gia presenti su contenuti bloccati e DRM restano applicati.

Test online Android/JVM del resolver: Rrushe 1, Schengen Visa 1, Egjeli 61, Kafeneja Jone ritorno 2017 episodi 1 e 12, speciale Gezuar 2020. Tutti risolti e relativi manifest verificati come HLS. Controllo esteso completato: 111 episodi Gjirafa, 111 manifest principali e 111 playlist video con risposta HTTP 200 e formato HLS; 20 tramite API ufficiale di firma, 91 tramite manifest pubblico della pagina originale. I risultati del controllo esteso sono in `gjirafa-playback-verified/`: ciascuna riga conserva solo pagina originale, ID e risultato HTTP; nessun URL firmato persistente. Questi controlli verificano accesso ai manifest, non la visione integrale di ogni episodio. Il rinnovo a scadenza e implementato, ma non e stato provato attendendo 40 minuti su un episodio intero.

La correzione del resolver richiede l'app ricompilata: il solo aggiornamento del config non cambia il codice delle app gia installate.

## Ordine

Il precedente ordinamento alfabetico metteva la stagione 10 prima della 2. Le stagioni ora sono ordinate numericamente e gli episodi al loro interno per numero. Titoli romani come `Sezoni i V-te` ora vengono letti come stagione 5, non stagione 1; questo corregge anche collocazioni e collisioni di Cka ka shpija. Le raccolte iniziali precedono le stagioni numerate; Reality e gli speciali restano separati.

Fara e flliqt aveva due sequenze nello stesso gruppo generico: episodi iniziali 1-15 e numerazione successiva 100-186. Ora l'ordine e:

1. Epizodat 1-15.
2. Stagioni 2, 3, 4, 5, 6, con i numeri locali originali.
3. Epizodat 100-186, con i numeri cumulativi pubblicati dal canale.
4. Speciale.

Non vengono inventate stagioni 7 e successive per gli episodi 100-186. Il primo blocco rimane denominato per intervallo, poiche i titoli pubblicati non ne indicano esplicitamente la stagione. I buchi nelle stagioni locali restano tali.

O sa mire: raccolta originale 1-183, ritorno Reality, speciale. Cka ka shpija: raccolta iniziale per intervallo, stagioni documentate in ordine numerico, speciali. Egjeli: blocco HD, blocco 2016, tre stagioni del ritorno, con preferenza alle alternative ufficiali YouTube gia censite quando disponibili. L'episodio 1 senza anno viene associato al blocco 2016 in base alla posizione consecutiva nell'inventario ufficiale STUPCAT prima degli episodi 2-15 con anno 2016: e una ricostruzione dall'ordine del canale, non una stagione nuova dichiarata. Schengen Visa: tre stagioni nell'ordine ufficiale. Rrushe e Njerez dhe fate: numerazione crescente. Kafeneja Jone non e stata ricensita o riorganizzata.

Gli audit JSON aggiornati conservano fonti alternative e lacune. Le raccolte non sono dichiarate complete. I test verificano anche l'ordine numerico delle stagioni, l'assenza di numeri duplicati in ciascun gruppo e la separazione delle due sequenze di Fara. Test unitari e compilazione debug completati; APK non pubblicato.
