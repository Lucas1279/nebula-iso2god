# Nebula ISO2GOD

A 100% in-browser Xbox 360 ISO to Games on Demand (GOD) converter for
modded JTAG/RGH consoles. The whole converter is the single `index.html`
file -- open it locally or host it anywhere static.

It also includes an unchanged XBLA/XBLIG uploader and a PS1 multi-BIN
merger that turns a Redump-style `.cue` plus `(Track N).bin` game folder
into one matched `.bin` + `.cue` pair for PCSXR360 2.1.1b. PS1 merging
is lossless concatenation with recalculated cue indexes—not compression.

This folder is laid out for GitHub Pages: upload these files to the root
of a public repository, enable Pages (Settings -> Pages -> Deploy from
branch `main`, folder `/ (root)`), and the site will be live at:

    https://YOUR-USERNAME.github.io/REPOSITORY-NAME/

Only use it with backups of games you own.
