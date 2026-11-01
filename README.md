# TSMA Kit

TSMA Kit turns an Ubuntu PC into a standalone guitar rig using a **Tone Shifter pedalboard/audio interface, ToneLib GFX and SooperLooper**. It is designed for practice and live performance, with hardware control of presets, effects and loops.

The current audio and MIDI profile was tested with a **MeloAudio Tone Shifter Mega** and an **M-Wave Chocolate connected over USB**. Other Tone Shifter models need their audio ports and MIDI messages checked before using this profile.

## How it works

```text
Guitar → Tone Shifter input L → ToneLib GFX → SooperLooper → Tone Shifter outputs
```

The launcher starts JACK if needed and opens a single **TSMA Kit** window: **ToneLib on top, SooperLooper below**, aligned to the same width without internal title bars. The window can be moved, resized and minimized as one application.

ToneLib handles the sound; SooperLooper records, plays and overdubs loops. The kit reconnects its audio and MIDI paths when devices or applications return. It uses 48 kHz audio, a 256-frame JACK buffer and one stereo loop with up to 300 seconds of memory per channel.

**Ardour is optional and is never launched by the kit.** If an already-running Ardour session exposes the stereo inputs of a track named `TSMA-Kit`, the kit routes its output to that track. Otherwise it monitors through the Tone Shifter outputs. The Ardour session must provide its own monitoring/output routing.

## Pedal controls

| Controller | Button | Action |
|---|---|---|
| Tone Shifter Mega | 1 / 2 | Previous / next ToneLib preset |
| Tone Shifter Mega | 3 / 4 | Select the hardware page for effects 1–4 / 5–8 |
| Tone Shifter Mega | A–D | Toggle the corresponding effect on the selected page |
| M-Wave Chocolate | A | Record an empty loop; press again to finish and play. With an existing loop, play/retrigger it. |
| M-Wave Chocolate | B | Overdub on/off |
| M-Wave Chocolate | C | Pause/resume |
| M-Wave Chocolate | D | Clear the loop |

To record a replacement loop: **D → A → play your guitar → A**. Page selection on the TS Mega is reported by the next A–D message. The current mapping controls up to eight effects in chain order.

The Chocolate must use its saved Custom CC profile: MIDI channel 1, CC 80/81/82/83 for A/B/C/D, momentary 127/0. The kit handles presses and ignores releases. It does not reprogram the hardware.

## Install and run

The supported installation target is an **Ubuntu/Debian/Mint x86_64 desktop** with a user systemd session and X11 or XWayland. The bundled profile has been tested locally; each new PC still needs an audio, latency and USB reconnect check before live use.

1. Install and activate [ToneLib GFX](https://tonelib.net/downloads.html) separately. The proprietary application and its license are **not included** in this repository. The setup was tested with ToneLib GFX 4.9.
2. Clone the repository and run the installer as your normal desktop user:

   ```bash
   git clone https://github.com/somotechsrl/TSMA-Kit.git
   cd TSMA-Kit
   ./Installa-TSMA
   ```

   The installer installs missing system dependencies with `sudo`, builds the MIDI adapter and menu lock module, imports the saved ToneLib settings/preset slots, and creates a desktop icon. Existing ToneLib configuration is backed up under `~/.local/share/tsma-kit/backups/` before import. Use `./Installa-TSMA --keep-profile` to retain an existing profile instead.
3. Connect both pedalboards, plug the guitar into input L, connect headphones or amplification to the Tone Shifter, and open the **TSMA Kit** desktop icon or run:

   ```bash
   ./Avvia-TSMA
   ```

The folder can be moved. Stop the kit before moving it and rerun the installer to update the desktop icon. On another Linux distribution, install the dependencies yourself and use `./Installa-TSMA --no-deps`. ARM is not supported by the tested ToneLib application.

## Performance interface and saved data

The SooperLooper menu is hidden and disabled, and its menu accelerators are removed. A clickable guard covers ToneLib's preferences button, while common preferences shortcuts are intercepted inside the container. These controls prevent accidental configuration changes during performance; they are not an access-control boundary. For maintenance, stop the kit and open the original applications outside the container.

- `Salva-loop` requests a loop save. The engine also saves after recording/overdub finishes and when pausing; a saved loop is restored paused.
- `Salva-config` exports the current preset slots and musical settings into this source tree, excluding personal paths, recordings and registration files. Review preset/IR content before publishing further changes.
- `Arresta-TSMA`, or closing the container window, stops the kit gracefully. JACK and external applications remain separate.
- `state/` holds local SooperLooper session/audio data; `log/` holds diagnostics. Both are ignored by Git.

The repository includes the saved preset parameter slots and MIDI mappings. **Recorded loops, registration credentials, proprietary binaries and external impulse-response audio are excluded.** Presets that use external IRs need those IRs installed locally. The existing private portable kit retains the full personal configuration.

## Development checks

```bash
python3 -m unittest discover -s tests -v
python3 -m unittest discover -s config/Jack/Drivers.d/tests -v
cc -Wall -Wextra -Werror -O2 config/Jack/Drivers.d/tsmega-midi.c \
  -Wl,-l:libasound.so.2 -o /tmp/tsma-midi-check
/tmp/tsma-midi-check --self-test
```

These checks run without audio hardware. The source of the SooperLooper GTK menu lock is in `src/slgui-lock.c`; the nested GUI is managed by `bin/gui.py` using GTK3, Xephyr and Openbox.
