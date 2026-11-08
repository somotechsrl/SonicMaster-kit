# SonicMaster-kit

Kit per Ubuntu con **Pocket Master USB → SooperLooper → traccia Ardour `TSMA-Kit`**, derivato da [TSMega-kit](https://github.com/somotechsrl/TSMega-kit). L'editor è **SonicMaster**, dedicato al Pocket Master; l'elaborazione degli effetti avviene nel pedale.

Il Pocket Master lavora a **44,1 kHz stereo**. Il ponte Zita ricampiona verso JACK a **48 kHz / 256 frame**, riutilizzando i bridge già presenti. Ardour resta separato: il kit non lo avvia e non arresta il server JACK alla chiusura. I due kit condividono Chocolate e traccia: usare un kit alla volta.

## Uso

```bash
./install-sonicmaster --no-deps  # se le dipendenze sono già installate
./start-sonicmaster
./stop-sonicmaster
```

L'icona **SonicMaster-kit** è distinta da SonicMaster e da TSMega-kit. La finestra contiene SonicMaster, SooperLooper e la legenda MIDImix. Tastiera e puntatore restano allineati anche ridimensionando la finestra.

- **Pocket Master:** selezione USB automatica, limitata al nome esatto `Pocket Master`. La versione dedicata legge il preset attivo senza cambiarlo e riprova la connessione USB dopo un distacco.
- **Chocolate USB (SINCO):** A/CC80 Record-Play, B/CC81 Overdub, C/CC82 Pausa-Riprendi, D/CC83 Cancella. Le pressioni inviano i comandi; i rilasci vengono ignorati. `Check` conserva verifica e programmazione assistita con backup.
- **Drums:** scelta e avvio delle basi locali, volume in dB e Stop. Il player JACK separato entra nel mix dopo il looper; le basi non vengono registrate nei loop. Cartella e volume sono persistenti.
- **MIDImix:** stessi banchi, nomi, mute, meter e punto di aggancio a 0 dB di TSMega-kit; Ardour rimane opzionale.
- **Ardour:** collegamento automatico a `TSMA-Kit` quando entrambi gli ingressi stereo esistono. Altrimenti ascolto dalle uscite Pocket Master.
- **OBS:** quando Ardour è chiuso, il mix viene inoltrato anche al ponte PipeWire JACK già presente. In OBS selezionare **JACK Source** nella cattura audio PulseAudio. Non vengono creati loopback né avviato OBS.

Loop e sessione del kit restano in `state/`; preferenze della finestra e delle basi in `~/.config/sonicmaster-kit/`. Le impostazioni di SonicMaster sono in `~/.local/share/dev.skyggedans.sonicmaster/`. I preset User sono nella memoria del pedale; usare Export per copie JSON.

## Preset adattati da ToneLib

`presets/source/tonelib-summaries.json` conserva le impostazioni esportate dal programma originale. `presets/pocket-master/` contiene **17 adattamenti**, **33 inizializzazioni bypass** e un manifest con tutte le differenze.

I 17 suoni sono etichettati consecutivamente **1A…5A**, senza spazi o zero iniziale. La numerazione usa gruppi di quattro: **1A=P01, 1D=P04, 2A=P05, …, 5A=P17**. Il nome sul pedale ha un limite di 10 caratteri; i file conservano la descrizione completa. I 50 Factory sono separati e non vengono scritti.

Gli adattamenti non sono copie acusticamente identiche: modelli, scale e numero di blocchi differiscono. Le casse per basso originali non sono disponibili nei modelli Pocket Master: l'IR resta bypassato per conservare la gamma bassa. Pickup Mod, IR esterni e catene parallele non trasferibili sono segnalati nel manifest. I livelli sono ricentrati e richiedono rifinitura all'ascolto.

```bash
python3 bin/adapt_presets.py  # genera file, non invia MIDI
python3 bin/write_user_bank.py --backup /percorso/backup  # mostra il piano
# Solo su richiesta esplicita: --apply scrive i 50 slot User con verifica da flash.
```

Il programma richiede un backup completo dei 50 slot prima di scrivere, verifica CRC, parametri, modelli e nomi dopo il caricamento da memoria e registra gli esiti. `bin/pocket_bank.py` accetta esclusivamente il Pocket Master USB. Le funzioni di scrittura del banco non vengono chiamate dal normale launcher.

## Editor dedicato e sviluppo

L'editor deriva da **SonicMaster v1.0.10**, commit `931a68f4ee06263e1eb622ee0fccf9f84d2b9751`. La patch riproducibile è in `editor/sonicmaster-pocket-only.patch`. Include selezione esclusiva USB Pocket Master, riconnessione, richiesta di lettura dello slot attivo e decodifica TLV di stato/modelli/parametri indipendente dalla frammentazione USB. La compilazione locale è stata verificata con Flutter 3.47.9. L'applicazione SonicMaster installata separatamente non viene sostituita.

Per ricompilare: `python3 editor/build.py --flutter /percorso/flutter/bin/flutter`. Serve Flutter/Dart compatibile con Dart 3.12.2+, clang, CMake, Ninja, GTK3 e ALSA development files. È possibile riusare la libreria DSP non modificata dell'installazione ufficiale 1.0.10 oppure compilare Rust con rustup. Il bundle locale va in `vendor/sonicmaster/`, escluso da Git.

Dipendenze runtime: Python3/GObject, GTK3, GStreamer (plugin JACK e decoder), JACK2, zita-ajbridge, SooperLooper, Xephyr, Openbox e gli strumenti X11. L'installer può installarle su Ubuntu/Debian. Il bundle locale è stato compilato su Ubuntu 24.04 x86_64; non viene promesso un runtime portabile per altre distribuzioni.

```bash
python3 -m unittest discover -s tests -p 'test_*.py'
python3 -m py_compile bin/*.py
```

Codice applicativo, configurazione e preset adattati sono versionati; audio personale, registrazioni, licenze, backup del pedale e binari generati restano locali. Le licenze MIT di SonicMaster e del codec pocket-master-mcp sono in `LICENSES/`.
