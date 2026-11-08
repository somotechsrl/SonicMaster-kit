# Packaging SonicMaster-kit

This derived kit runs natively on Ubuntu 24.04. It does not use the former ToneLib installer or release workflow. Build the MIT-licensed Pocket-only editor using `editor/build.py`, then run `./install-sonicmaster`. Compiled editor files are kept in `vendor/sonicmaster/`; the installer builds `vendor/slgui-lock.so`.

Source archives can be generated after a commit with `git archive --format=tar.gz -o SonicMaster-kit-source.tar.gz HEAD`. They omit personal audio, pedal backups, state and generated binaries. The editor build remains reproducible from the pinned upstream commit and patch; no GitHub CI/deploy is enabled.
