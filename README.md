# Nebula ISO2GOD

A 100% in-browser Xbox 360 ISO to Games on Demand (GOD) converter for
modded JTAG/RGH consoles. The main interface is `index.html`, designed for static hosting. Keep `data/disc_catalog.json` at that exact relative path and the bundled `vendor/un7z-opfs/` files beside it; the catalogue supplies offline Title ID + Media ID disc recognition and validated role rules. Keep the catalogue available for ISO processing; open the page through HTTPS or the local helper, not as `file://`.

It also includes an XBLA/XBLIG uploader, a PS1 multi-BIN merger that turns a Redump-style `.cue` plus `(Track N).bin` game folder into one matched `.bin` + `.cue` pair for PCSXR360 2.1.1b, a SNES360 ROM uploader that copies `.sfc`/`.smc` and other common SNES ROMs unchanged (including locally unpacked `.7z` archives), and an optional local-network Xbox FTP file manager for browsing, uploading, moving remote files by drag-and-drop, importing files to the computer, supported-browser desktop drag-out with actual file bytes, and editing `launch.ini`. PS1 merging is lossless concatenation with recalculated cue indexes—not compression. The FTP manager and all four game-tool FTP upload flows require the local `ftp_helper.py`; the static GitHub Pages site alone cannot connect to raw FTP.

This folder is laid out for GitHub Pages: upload these files to the root
of a public repository, enable Pages (Settings -> Pages -> Deploy from
branch `main`, folder `/ (root)`), and the site will be live at:

    https://YOUR-USERNAME.github.io/REPOSITORY-NAME/

## Xbox 360 disc catalogue

The converter loads `data/disc_catalog.json` locally and exact-matches XEX Title ID + Media ID. Its identity crosswalk currently has 2,577 exact records. Role matching is sourced from the 2026-10-30 Redump Xbox 360 DAT (3,733 named media); Vimm's Xbox 360 Vault reports 3,714/3,733 media and says it syncs nightly with Redump. Only explicitly sourced role labels are automated (31 exact Media-ID rules); any unknown executable-disc role keeps the themed chooser. These larger source counts do not equal exact XEX identity/role coverage, so an absent entry is not proof of a disc's role. To rebuild it from the included Redump DAT and game-list CSV, run `python3 build_disc_catalog.py`, inspect `data/disc_catalog_review.md`, then run `python3 -m unittest test_disc_catalog.py test_ftp_helper.py` before rebuilding download archives with `python3 rebuild_bundles.py`.

Only use it with backups of games you own.
