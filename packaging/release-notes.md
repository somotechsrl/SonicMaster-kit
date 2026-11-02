TSMA Kit 1.0.8

- Compact bank/effect indicator beside Drums and Check, for example `Banco: 5–8 · Effetto: 1 → 5`. The effect number is relative to the bank and absolute within the mapping.
- All 128 Program Change positions are displayed in groups of four. The pedal's flashing bank prefix is pending; the indicator updates when A–D confirms it.
- ToneLib exposes eight native assignment controls. Positions beyond effect 8 are marked `non assegnato` and ignored, instead of wrapping onto effects 1–8 or triggering looper actions. Extended numbering does not add further native ToneLib controls.
- Drums loads tracks in the background and starts playback after ToneLib finishes its own audio-file check. Progress dialogs keep their normal size.
- Check learns the complete first-bank Program Change offset, without reducing it modulo eight.

Window size/position persistence, the Check pedal utility, the compact SooperLooper panel and the tested USB audio fix are retained. Effect names and live on/off feedback are not included.

Downloads: self-contained x86_64 AppImage, DEB and RPM, corresponding runtime sources and SHA-256 checksums. Requires glibc 2.35+, systemd user services and X11/XWayland. ToneLib is downloaded separately from its official vendor. No personal license, registration or backing-track audio is included.
