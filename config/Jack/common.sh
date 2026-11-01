#!/bin/bash
# Funzioni condivise dagli hook di QjackCtl: JACK gestisce i dispositivi ALSA.
# PipeWire/PulseAudio può restare attivo esclusivamente come ponte verso JACK.
JACK_DIR=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
JACK_STATE_DIR="${XDG_RUNTIME_DIR:-/tmp}/jack-hooks-$UID"
(umask 077; mkdir -p -- "$JACK_STATE_DIR") || return 1
warn() { printf 'JACK: %s\n' "$*" >&2; }

# Non sospendere jack_sink: sospendere tutto il server audio elimina il ponte.
# Si rilasciano soltanto eventuali dispositivi ALSA gestiti da PulseAudio.
suspend_alsa() {
    local action=$1 id name rest
    command -v pactl >/dev/null || return 0
    while read -r id name rest; do
        [[ $name == alsa_output.* ]] || continue
        pactl suspend-sink "$id" "$action" || warn "Impossibile sospendere/ripristinare $name"
    done < <(pactl list short sinks)
    while read -r id name rest; do
        [[ $name == alsa_input.* ]] || continue
        pactl suspend-source "$id" "$action" || warn "Impossibile sospendere/ripristinare $name"
    done < <(pactl list short sources)
}

# Il PID viene verificato prima dell'arresto per evitare di colpire un PID riusato.
stop_drivers() {
    local pid cmd attempt
    [[ -r $JACK_STATE_DIR/drivers.pid ]] || return 0
    read -r pid < "$JACK_STATE_DIR/drivers.pid"
    [[ $pid =~ ^[0-9]+$ ]] || return 0
    cmd=$(tr '\0' ' ' < "/proc/$pid/cmdline" 2>/dev/null) || return 0
    [[ $cmd == *"$JACK_DIR/Drivers"* ]] || return 0
    kill -TERM "$pid" 2>/dev/null || :
    # Attendere la pulizia dei bridge prima che QjackCtl arresti il server.
    for attempt in {1..50}; do
        [[ -e $JACK_STATE_DIR/drivers.pid ]] || return 0
        sleep 0.1
    done
    warn "Il gestore driver non ha completato lo stop entro 5 secondi"
    return 1
}

# Preferire jack_sink quando il ponte è disponibile; non creare loopback verso
# nomi di dispositivi inesistenti (il vecchio zoom_out non è presente).
select_jack_sink() {
    local attempt
    command -v pactl >/dev/null || return 0
    for attempt in {1..20}; do
        if pactl list short sinks | awk '$2 == "jack_sink" { found=1 } END { exit !found }'; then
            pactl set-default-sink jack_sink
            return
        fi
        sleep 0.25
    done
    warn "jack_sink non disponibile: verificare il ponte desktop verso JACK."
}
