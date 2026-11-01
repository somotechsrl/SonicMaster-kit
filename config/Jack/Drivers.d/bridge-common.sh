#!/bin/bash
# Libreria comune dei gestori: configurazione, comandi, lock e stop ordinato.
JACK_DRIVERS_DIR=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
source "$JACK_DRIVERS_DIR/../common.sh" || return 1
source "${JACK_DRIVERS_CONFIG:-$JACK_DRIVERS_DIR/Drivers.conf}" || return 1
export MONITOR_AUTO_RESTART MONITOR_WARMUP MONITOR_SUSTAIN MONITOR_ERROR_SAMPLES
export MONITOR_RATIO_SPAN_PPM MONITOR_RATIO_LIMIT_PPM MONITOR_COOLDOWN
export MONITOR_MAX_RESTARTS MONITOR_RESTART_WINDOW
[[ $MONITOR_ENABLED =~ ^[01]$ ]] || { warn "MONITOR_ENABLED non valido"; return 1; }
if [[ $MONITOR_ENABLED == 1 ]]; then
    command -v python3 >/dev/null && command -v stdbuf >/dev/null || return 1
    python3 "$JACK_DRIVERS_DIR/Monitor" --check >/dev/null || return 1
fi
bridge_mode=${1:-run}
case "$bridge_mode" in run|--check|--show) ;; *) warn "Uso: $0 [--check|--show]"; return 2 ;; esac
bridge_children=()
bridge_pidfile=
bridge_cleanup() {
    trap '' TERM INT
    if ((${#bridge_children[@]})); then
        kill -TERM "${bridge_children[@]}" 2>/dev/null || :
        wait "${bridge_children[@]}" 2>/dev/null || :
    fi
    [[ -z $bridge_pidfile ]] || rm -f -- "$bridge_pidfile"
}
bridge_begin() {
    local name=$1
    [[ $bridge_mode == run ]] || return 0
    exec 8>"$JACK_STATE_DIR/$name.lock"
    flock -n 8 || { warn "$name già avviato"; exit 0; }
    bridge_pidfile="$JACK_STATE_DIR/$name.pid"
    printf '%s\n' "$$" > "$bridge_pidfile"
    trap bridge_cleanup EXIT
    trap 'exit 0' TERM INT
}
bridge_command() {
    local backend=$1 direction=$2 device=$3 client=$4 channels=$5 period=$6 periods=$7 stereo=${8:-0}
    local number command
    case "$backend:$direction" in
        zita:in) command=zita-a2j ;; zita:out) command=zita-j2a ;;
        alsa:in) command=alsa_in ;; alsa:out) command=alsa_out ;;
        *) warn "Backend/direzione non valido per $client: $backend/$direction"; return 1 ;;
    esac
    for number in "$AUDIO_RATE" "$channels" "$period" "$periods"; do
        [[ $number =~ ^[1-9][0-9]*$ ]] || { warn "Parametro audio non valido per $client: $number"; return 1; }
    done
    [[ $ALSA_QUALITY =~ ^[0-4]$ && $BRIDGE_TRACE =~ ^[01]$ ]] || { warn "Quality/trace non valido"; return 1; }
    [[ -n $device ]] || { warn "Dispositivo vuoto per $client"; return 1; }
    command -v "$command" >/dev/null || { warn "Comando assente: $command"; return 1; }
    bridge_args=("$command" -r "$AUDIO_RATE" -p "$period" -n "$periods" -c "$channels" -d "$device" -j "$client")
    if [[ $backend == alsa ]]; then bridge_args+=(-q "$ALSA_QUALITY");
    elif [[ $stereo == 1 ]]; then bridge_args+=(-L); fi
    [[ $BRIDGE_TRACE == 0 ]] || bridge_args+=(-v)
}
bridge_add() {
    bridge_command "$@" || return 1
    case "$bridge_mode" in
        --check) return 0 ;;
        --show) printf '%q ' "${bridge_args[@]}"; printf '\n'; return 0 ;;
    esac
    warn "Avvio ${bridge_args[*]}"
    if [[ $1 == zita && $MONITOR_ENABLED == 1 ]]; then
        python3 "$JACK_DRIVERS_DIR/Monitor" --run --client "$4" -- "${bridge_args[@]}" 8>&- 9>&- &
    else
        "${bridge_args[@]}" 8>&- 9>&- &
    fi
    bridge_children+=("$!")
}
bridge_wait() {
    [[ $bridge_mode == run ]] || return 0
    local child owner=${JACK_DRIVERS_OWNER_PID:-} owner_start=
    if [[ -n $owner ]]; then
        owner_start=$(awk '{print $22}' "/proc/$owner/stat") || return 1
    fi
    while :; do
        if [[ -n $owner && $(awk '{print $22}' "/proc/$owner/stat" 2>/dev/null) != "$owner_start" ]]; then
            return 0
        fi
        for child in "${bridge_children[@]}"; do
            if ! kill -0 "$child" 2>/dev/null; then
                wait "$child"; local status=$?
                warn "Bridge del gestore terminato (PID $child, stato $status)"
                return 1
            fi
        done
        sleep 0.25
    done
}
