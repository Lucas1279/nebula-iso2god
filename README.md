# Nebula ISO2GOD

A 100% in-browser Xbox 360 ISO to Games on Demand (GOD) converter for
modded JTAG/RGH consoles. The main interface is `index.html`, designed for static hosting. Keep the bundled `vendor/un7z-opfs/` files beside it to enable local `.7z` archive import; open the page through HTTPS or the local helper, not as `file://`.

It also includes an XBLA/XBLIG uploader, a PS1 multi-BIN merger that turns a Redump-style `.cue` plus `(Track N).bin` game folder into one matched `.bin` + `.cue` pair for PCSXR360 2.1.1b, a SNES360 ROM uploader that copies `.sfc`/`.smc` and other common SNES ROMs unchanged (including locally unpacked `.7z` archives), and an optional local-network Xbox FTP file manager for browsing, uploading, and deleting remote files. PS1 merging is lossless concatenation with recalculated cue indexes—not compression. The FTP manager and all four game-tool FTP upload flows require the local `ftp_helper.py`; the static GitHub Pages site alone cannot connect to raw FTP.

This folder is laid out for GitHub Pages: upload these files to the root
of a public repository, enable Pages (Settings -> Pages -> Deploy from
branch `main`, folder `/ (root)`), and the site will be live at:

    https://YOUR-USERNAME.github.io/REPOSITORY-NAME/

Only use it with backups of games you own.
