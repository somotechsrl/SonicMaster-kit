# Bridge JACK modulari

## Tone Shifter Mega

`TSMEGA` espone due ingressi `TSMEGA_in:capture_1/2` e due uscite
`TSMEGA_out:playback_1/2`, con Zita a 48 kHz, 256 campioni e due periodi.
L'ingresso chitarra L corrisponde a `capture_1`. Il dispositivo usa il nome
ALSA stabile `hw:CARD=TSMEGA,DEV=0`; il formato nativo conserva i 24 bit
del convertitore senza l'opzione Zita `-L`.

È incluso nel gestore centrale e nel monitor dei bridge. Le opzioni
`TSMEGA_ENABLED`, `TSMEGA_DEVICE`, `TSMEGA_RATE`, `TSMEGA_PERIOD`,
`TSMEGA_PERIODS` e i backend per direzione sono in `Drivers.conf`.
Il MIDI rimane disponibile tramite il ponte a2j già esistente, come
`a2j:TSMEGA (capture): TSMEGA MIDI 1`.

Con `TSMEGA_TONELIB_ENABLED=1` il driver avvia anche l'adattatore MIDI e
il ripristino dei collegamenti dello standalone: `capture_1` alimenta entrambi
gli ingressi di `JUCEJack`, le uscite stereo alimentano la traccia Ardour `TTSM`.
Il monitoraggio passa quindi attraverso Ardour. ToneLib GFX va aperto in modalità
JACK; non viene avviato automaticamente dal driver.

Il profilo hardware attuale resta invariato. Sono accettati tutti i canali MIDI
provenienti dalla sola sorgente TSMEGA: il profilo provato trasmette anche sul
canale 2, quindi non si applica un filtro fisso sul canale 1.
1/2 (CC22/25) richiamano il preset precedente/successivo. Ogni messaggio conta
come una pressione, sia valore 0 sia 64: il profilo hardware alterna questi valori.
3/4 cambiano il banco interno senza inviare subito MIDI. Il successivo A–D
invia un PC che identifica banco e pulsante; il modulo otto seleziona Control 1–8.
PC0–3, 8–11, 16–19 ecc. = pagina 1 (effetti 1–4);
PC4–7, 12–15, 20–23 ecc. = pagina 2 (effetti 5–8).
Le pagine si alternano scorrendo i banchi con 3/4; non occorre riprogrammare
l'hardware e il riavvio dell'adattatore non perde la pagina.
L'uscita virtuale ALSA `ToneLib Controls` usa CC20/21 e CC24–31 sul canale 16,
con impulsi 127/0.
Il canale separato evita conflitti con i messaggi originali e con MIDI Mix.
L'adattatore ritrova sorgente TS e ingresso ToneLib per nome ogni due secondi.
Gli eventi arrivano direttamente all'ingresso ALSA `ToneLib Controls`: ToneLib
mantiene questo ingresso in cache e impedisce a processi esterni di ripristinare
la sottoscrizione quando l'adattatore viene ricreato. La consegna diretta evita
sia questa dipendenza sia eventi doppi in presenza della sottoscrizione iniziale.

I monitor TS riconoscono la scomparsa del PCM in `/proc/asound`, arrestano solo
il relativo ponte e attendono il ritorno USB, conservando l'ultimo grafo valido.
Il ritorno fisico avvia un nuovo recupero anche se restano collegamenti pendenti
del processo terminato; i normali limiti per anomalie di sincronizzazione restano
attivi. La funzione richiede monitor Zita e il nome ALSA `hw:CARD=...,DEV=...`.
Verifica del 1 novembre 2026: quattro collegamenti audio rimossi e ripristinati
in 1,15 s; sorgente MIDI rimossa e ripristinata in 0,22 s. Il caso USB assente e
ricollegato è coperto dai test simulati; nessuno scollegamento USB fisico eseguito.

Le assegnazioni globali sono salvate nelle preferenze di ToneLib. Nei 14 preset
con effetti presenti al momento della configurazione, Control 1–8 comandano gli
On/Off dei primi otto effetti, nell'ordine della catena (amplificatore e cassa
inclusi). Le posizioni assenti non hanno effetto. Santana Style - Drive ha nove
effetti: il nono resta nello stato salvato. I parametri sonori sono conservati.
I nuovi preset o le catene riordinate richiedono di aggiornare queste assegnazioni
con il pulsante MIDI di ToneLib. Il Chocolate M-Wave è configurato per il looper come descritto sotto.
Le copie complete prima delle pagine e il rapporto sono nella cartella di backup;
`prepare-pages.py` conserva la procedura con verifiche sui byte dei parametri.
`TSMEGA_MIDI_TRACE=1` abilita la diagnostica dei messaggi nell'adattatore.

`tsmega-midi.c` si ricompila con:
`cc -Wall -Wextra -O2 tsmega-midi.c -Wl,-l:libasound.so.2 -o tsmega-midi`.
`./tsmega-midi --self-test` controlla la traduzione. L'adattatore non scrive
impostazioni sul controller. Backup iniziale: `../backup-tsmega-20261101-103240/`.

## Chocolate M-Wave: SooperLooper

Il Chocolate standard USB (`SINCO`, diverso dal Plus) usa Custom CC mode 7,
canale 1, CC80/81/82/83 momentanei (127 pressione, 0 rilascio):

- A: Rec/Play SooperLooper.
- B: Overdub on/off.
- C: Pause/Resume.
- D: Clear.

L'adattatore inoltra le pressioni al socket del kit e ignora i rilasci.
Queste assegnazioni sostituiscono il precedente controllo del looper ToneLib,
del metronomo e del tuner. Le due pagine del Tone Shifter restano indipendenti.

Il pulsante **Check**, accanto a **Drums**, apre verifica MIDI, test guidato,
apprendimento delle assegnazioni software del Tone Shifter e programmazione
USB del Chocolate. La programmazione salva un backup e verifica ogni campo
con una rilettura. I dettagli e i limiti sono nel README principale, sezione
**Pedal Check and programming**.

Il test sospende le azioni MIDI dell'adattatore tramite una lease temporanea;
non ferma l'audio. Le assegnazioni software sono in `config/pedals.conf` e
vengono rilette ogni due secondi. L'adattatore di esecuzione non programma
mai direttamente l'hardware.

`../Drivers` è un file eseguibile, non un symlink. Avvia `UMC`, `A100`, `HDMI`
e il ponte MIDI. Ogni dispositivo ha lock e gestione dei propri processi.
`bridge-common.sh` contiene costruzione comandi, verifica e pulizia condivise.

## Configurazione

Modificare `Drivers.d/Drivers.conf`: `UMC_BACKEND`, `A100_BACKEND`, `HDMI_BACKEND`
accettano `zita` oppure `alsa`. Sono disponibili override separati per
`A100_IN_BACKEND`, `A100_OUT_BACKEND`, `HDMI_HEAD_BACKEND`, `HDMI_SPKR_BACKEND`.
Per disabilitare un dispositivo usare il relativo `*_ENABLED=0`.
I backend selezionano rispettivamente `zita-a2j`/`zita-j2a` oppure
`alsa_in`/`alsa_out`. Nomi delle porte e canali rimangono invariati.
Le impostazioni iniziali mantengono i parametri audio funzionanti.

`Drivers --check` verifica la configurazione senza aprire dispositivi.
`Drivers --show` mostra i comandi senza avviare audio.
Esempio: `UMC_BACKEND=alsa ./Drivers --show` dalla directory Jack.
`JACK_DRIVERS_CONFIG=/percorso/file.conf` permette un file alternativo.
`BRIDGE_TRACE=1` abilita la diagnostica dei bridge.

Gli hook esistenti `start-pst` e `stop-pre` continuano a usare `Drivers`.
Le modifiche si applicano al prossimo avvio: la sessione corrente non viene
interrotta. Non avviare i singoli script mentre è attivo un vecchio gestore:
solo il gestore modulare coordina i nuovi lock per ogni dispositivo.

## Monitor Zita

Il monitor viene avviato automaticamente per ogni bridge Zita. I backend ALSA
restano gestiti dai normali script. Non cambia i parametri audio del bridge.
Il monitor usa `-v` e output non bufferizzato, senza registrare l'audio.
Un unico lettore persistente (`Monitor --graph-server`) interroga il grafo
tramite libjack e un socket locale con permessi 600, evitando la creazione
continua di client JACK per il monitoraggio.

In `Drivers.conf`:

- `MONITOR_ENABLED=0`: disabilita completamente il monitor al prossimo avvio.
- `MONITOR_AUTO_RESTART=0`: osserva e registra senza riavviare automaticamente.
- `MONITOR_WARMUP=30`: ignora l'assestamento iniziale dopo ogni avvio.
- `MONITOR_SUSTAIN=10`: durata minima dell'anomalia numerica.
- `MONITOR_ERROR_SAMPLES=64`: limite dell'errore medio di sincronizzazione.
- `MONITOR_RATIO_SPAN_PPM=1000`: limite di escursione, con almeno tre attraversamenti tra gli estremi della finestra.
- `MONITOR_RATIO_LIMIT_PPM=10000`: limite dello scostamento della correzione da 1.
- `MONITOR_COOLDOWN=60`: pausa minima tra riavvii automatici del medesimo bridge.
- `MONITOR_MAX_RESTARTS=3`, `MONITOR_RESTART_WINDOW=600`: massimo 3 tentativi in 10 minuti.

Sono soglie conservative iniziali, non una diagnosi di tutti i rumori udibili.
Il rilevatore riconosce anche `NaN` e `Inf`: dopo warmup e durata minima
li considera un errore persistente, senza lasciare visibili vecchi valori validi.
`Monitor --status` legge anche l'ultima telemetria dai log e segnala
`telemetry_invalid`; funziona anche con monitor già in esecuzione prima
dell'aggiornamento. I valori non finiti vengono mostrati come `null`.
La correzione del rilevatore si applica al prossimo avvio dei monitor: aggiornare
i file o consultare lo status non riavvia né modifica i bridge audio attivi.
Il monitor interviene per errori persistenti, oscillazioni della correzione,
ripetute risincronizzazioni vicine a dati validi, tre attese Zita per errore
in 45 secondi, oppure uscita del processo.
Una normale differenza costante tra i clock non costituisce un'oscillazione.
L'assenza di telemetria non provoca riavvii: durante export/freewheel il bridge
può essere normalmente sospeso. I limiti impediscono riavvii continui. Un lock comune consente un solo
ripristino per volta; tutti i monitor rispettano la pausa di assestamento
dopo il riavvio di qualsiasi bridge. Un singolo picco che rientra non è
considerato un'oscillazione ripetuta.

Il riavvio riguarda **un solo bridge**, anche per A100 o HDMI: gli altri restano
attivi. Prima dello stop viene salvato il grafo reale delle sue connessioni,
poi le porte vengono attese e i collegamenti ripristinati e verificati.
Se JACK non risponde, non viene tentato un riavvio alla cieca. Se mancano porte
remote il ripristino resta in attesa e blocca ulteriori riavvii.
Un processo morto viene recuperato solo dopo aver raccolto uno snapshot; in
quel caso si usa l'ultimo snapshot disponibile, aggiornato ogni 10 secondi.
Il riavvio comporta una breve interruzione audio, senza chiudere Ardour.
Lo stop usa SIGINT, gestito da Zita per chiudere ordinatamente ALSA/JACK;
solo se non termina entro 3 secondi viene usato un arresto forzato.

Dalla cartella `Jack`:

```bash
./Drivers.d/Monitor --status
./Drivers.d/Monitor --restart U192k_in
./Drivers.d/Monitor --restart A100_in
./Drivers.d/Monitor --restart A100_out
./Drivers.d/Monitor --restart hdmi_head
./Drivers.d/Monitor --restart hdmi_spkr
```

Lo status riporta PID, errore in campioni, rapporto di ricampionamento,
escursione in ppm, warmup, riavvii e collegamenti ancora da ripristinare.
Log, stato e snapshot sono in `${XDG_RUNTIME_DIR:-/tmp}/jack-hooks-$UID`:
`U192k_in.log`, `A100_in.log`, `A100_out.log`, `hdmi_head.log`, `hdmi_spkr.log`.
Ogni log ha rotazione a 1 MiB con due copie; stato e snapshot hanno permessi 600.
Le richieste manuali usano il medesimo salvataggio/ripristino; non si applicano
ai bridge avviati senza monitor. Le nuove soglie si applicano al prossimo avvio.

## Disposizione

`Jack/Drivers`: entry point centrale.
`Jack/Drivers.d/`: dispositivi, configurazione, libreria e questa guida.

## Jamulus

`Jamulus` attende le porte del client e di Ardour e collega automaticamente
`Jamulus:output left/right` alla traccia `Jamulus OUT` e il bus `Jamulus IN`
a `Jamulus:input left/right`. Riutilizza il lettore persistente del grafo di
`Monitor`. Funziona anche se Ardour viene avviato dopo Jamulus e ripete
l’aggancio quando uno dei due client torna disponibile. Non avvia Jamulus.
Dopo l’assestamento non forza nuovamente le modifiche manuali dell’utente.

`JAMULUS_ENABLED=0` disabilita il modulo. Nomi configurabili con
`JAMULUS_CLIENT`, `JAMULUS_DAW_CLIENT`, `JAMULUS_INPUT_TRACK`,
`JAMULUS_OUTPUT_BUS` in `Drivers.conf`. `JAMULUS_REMOVE_SYSTEM=1` elimina
solo i collegamenti automatici diretti tra Jamulus e `system:capture_*` /
`system:playback_*`, dopo avere verificato i quattro collegamenti Ardour;
0 mantiene anche questi collegamenti. Gli altri collegamenti restano intatti.

`./Drivers.d/Jamulus --check` e `--show` non cambiano il grafo.
Il gestore lo avvia automaticamente ai prossimi avvii JACK; è avviabile
anche da solo con `./Drivers.d/Jamulus` mentre il lettore del grafo è attivo.
Log con rotazione: `${XDG_RUNTIME_DIR:-/tmp}/jack-hooks-$UID/jamulus-routing.log`.


## JackTrip

`JackTrip` usa lo stesso monitor e algoritmo di routing di Jamulus, con le porte
native `receive_1/2` verso la traccia stereo `FR JackTrip` e il bus `TO JackTrip`
verso `send_1/2`. Servono entrambi i percorsi stereo: il modulo attende finché
client e porte Ardour sono presenti. Non crea tracce nella sessione.

`JACKTRIP_ENABLED=1` abilita il modulo al prossimo avvio dei driver.
Configurazione: `JACKTRIP_CLIENT`, `JACKTRIP_DAW_CLIENT`,
`JACKTRIP_INPUT_TRACK`, `JACKTRIP_OUTPUT_BUS`, `JACKTRIP_REMOVE_SYSTEM`.

Sul PC `~/.local/bin/jacktrip-ardour on|off|status` salva la preferenza e
applica ON/OFF senza riavviare JACK o gli altri driver. OFF ferma il monitor;
lascia intatti i collegamenti già presenti, come il modulo Jamulus.
ON non avvia il client audio. `~/.local/bin/jacktrip-jam start|stop|status`
controlla invece il client; start rispetta la preferenza di autoconnect.
I comandi sono disponibili anche nel menu applicazioni.

## Carla esterna

`Carla` riutilizza il monitor e il routing condiviso di Jamulus e JackTrip:
`Carla:audio-out1/2` → `ardour:Carla OUT/audio_in 1/2`;
`ardour:Carla IN/audio_out 1/2` → `Carla:audio-in1/2`.
Attende entrambi i programmi e ripete l'aggancio quando le porte ricompaiono.
Dopo l'assestamento rispetta le modifiche manuali. Non avvia Carla, non crea
tracce e non modifica le connessioni MIDI o gli altri client.

Il gestore centrale lo avvia automaticamente con `CARLA_ENABLED=1`.
Nomi e comportamento sono configurabili con `CARLA_CLIENT`,
`CARLA_DAW_CLIENT`, `CARLA_INPUT_TRACK`, `CARLA_OUTPUT_BUS` e
`CARLA_REMOVE_SYSTEM` in `Drivers.conf`. Con `CARLA_REMOVE_SYSTEM=1`,
solo i collegamenti audio diretti Carla ↔ `system:capture_*`/`system:playback_*`
vengono rimossi, dopo la verifica dei quattro collegamenti Ardour.
`CARLA_REMOVE_SYSTEM=0` conserva anche i collegamenti hardware diretti.

`./Drivers.d/Carla --check` e `--show` non modificano le connessioni.
Log: `${XDG_RUNTIME_DIR:-/tmp}/jack-hooks-$UID/carla-routing.log`.

## Sonicake Pocket Master

`PocketMaster` aggiunge due canali di ingresso (`PocketMaster_in:capture_1/2`)
e due di uscita (`PocketMaster_out:playback_1/2`). È integrato in `Drivers` e
nel monitor Zita, con lock e arresto ordinato come gli altri dispositivi.
Non crea collegamenti audio automatici.

Il dispositivo USB `84ef:0284` è esposto da ALSA come `hw:CARD=Master,DEV=0`.
Supporta stereo S16_LE a 44100 Hz: il modulo usa questa frequenza hardware e
Zita con `-L`; il server JACK può continuare a funzionare a 48000 Hz.
La frequenza degli altri dispositivi non viene modificata.

Configurazione in `Drivers.conf`: `POCKET_MASTER_ENABLED`,
`POCKET_MASTER_BACKEND` (`zita` predefinito, oppure `alsa`),
`POCKET_MASTER_IN_BACKEND`, `POCKET_MASTER_OUT_BACKEND`,
`POCKET_MASTER_DEVICE`, `POCKET_MASTER_RATE`, `POCKET_MASTER_PERIOD`
e `POCKET_MASTER_PERIODS`. Impostare `POCKET_MASTER_ENABLED=0` per escluderlo.

`./Drivers.d/PocketMaster --check` verifica la configurazione;
`./Drivers.d/PocketMaster --show` mostra i comandi.
`./Drivers.d/Monitor --restart PocketMaster_in` / `PocketMaster_out`
richiedono il riavvio del singolo bridge con ripristino delle connessioni.
Il gestore lo avvia automaticamente dal successivo avvio JACK; se JACK è già
attivo si può eseguire `./Drivers.d/PocketMaster` senza riavviare gli altri driver.
