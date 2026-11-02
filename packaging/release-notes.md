TSMA Kit 1.0.9

- Fix startup crashes on Wayland desktops: the kit window selects XWayland before GTK initializes, so the embedded Xephyr display receives X11 window IDs. X11 desktop sessions remain supported.
- Show the current effect name beside its bank and position, for example `Banco: 5–8 · Effetto: 1 → 5 · Spring Rvb`, when ToneLib's native preset summary is available.
- Refresh effect names after pedal actions and preset changes; discard stale replies from earlier presets. The reader runs on the private application display and preserves its text clipboard.
- Retain all 128 displayed positions, the eight native ToneLib assignments, automatic drum playback, saved window geometry, Check pedal configuration and the USB audio fix.

Validation: offline regression tests, GTK smoke checks with X11 and inherited Wayland backend settings, and successful startup with ToneLib and SooperLooper in a Wayland desktop session.

Downloads: self-contained x86_64 AppImage, DEB and RPM, corresponding runtime sources and SHA-256 checksums. Requires glibc 2.35+, systemd user services, and X11 or a Wayland desktop with XWayland enabled. ToneLib is downloaded separately from its official vendor. No personal license, registration or backing-track audio is included.
