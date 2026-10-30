# Nebula ISO2GOD

A 100% in-browser Xbox 360 ISO to Games on Demand (GOD) converter for
modded JTAG/RGH consoles. The main interface is `index.html`, designed for static hosting. Keep `data/disc_catalog.json` at that exact relative path and the bundled `vendor/un7z-opfs/` files beside it; the catalogue supplies offline Title ID + Media ID disc recognition and validated role rules. Keep the catalogue available for ISO processing; open the page through HTTPS or the local helper, not as `file://`.

It also includes an XBLA/XBLIG uploader, a PS1 multi-BIN merger that turns a Redump-style `.cue` plus `(Track N).bin` game folder into one matched `.bin` + `.cue` pair for PCSXR360 2.1.1b, a SNES360 ROM uploader that copies `.sfc`/`.smc` and other common SNES ROMs unchanged (including locally unpacked `.7z` archives), and an optional local-network Xbox FTP file manager for browsing, uploading, moving remote files by drag-and-drop, importing files to the computer, supported-browser desktop drag-out with actual file bytes, and editing `launch.ini`. PS1 merging is lossless concatenation with recalculated cue indexes—not compression. The FTP manager and all four game-tool FTP upload flows require the local `ftp_helper.py`; the static GitHub Pages site alone cannot connect to raw FTP.

This folder is laid out for GitHub Pages: upload these files to the root
of a public repository, enable Pages (Settings -> Pages -> Deploy from
branch `main`, folder `/ (root)`), and the site will be live at:

    https://YOUR-USERNAME.github.io/REPOSITORY-NAME/

## Xbox 360 disc catalogue

The converter loads `data/disc_catalog.json` locally and exact-matches XEX Title ID + Media ID. The exact identity crosswalk currently has 2,577 records across 1,610 Title IDs. `data/redump_inventory.json` carries the full 3,733-entry Redump snapshot, including release names and hashes; title+disc joins are marked as review candidates only. Vimm's Xbox 360 Vault reports 3,714/3,733 media and says it syncs nightly with Redump. Only explicitly sourced role labels are automated (31 exact Media-ID rules); unknown roles keep the themed chooser. Redump/Vimm counts do not equal exact XEX identity/role coverage. To rebuild from the included DAT and game-list CSV, run `python3 build_disc_catalog.py`, inspect `data/disc_catalog_review.md` and the candidate links in `data/redump_inventory.json`, then run `python3 -m unittest test_disc_catalog.py test_ftp_helper.py` before rebuilding downloads with `python3 rebuild_bundles.py`.

Only use it with backups of games you own.
