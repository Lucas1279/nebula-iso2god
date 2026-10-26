# Nebula ISO2GOD — optional FTP upload

This build adds an **Upload to Xbox via FTP** output mode. Because GitHub Pages is a static HTTPS website and browsers cannot open raw FTP connections, FTP mode requires the small local Python helper included here. The helper serves this page at `http://127.0.0.1:8765/` and makes FTP connections from your PC to your Xbox.

## Start it (Windows, macOS, or Linux)

1. Install Python 3 if it is not already installed.
2. Keep `index.html` and `ftp_helper.py` together in the same folder.
3. Run `python ftp_helper.py` (Windows may use `py ftp_helper.py`). Keep the terminal window open. It should open the local app automatically; otherwise visit `http://127.0.0.1:8765/`.
4. On the Xbox 360, enable the FTP server in Aurora or FreeStyle Dash and note the console's **LAN IP**, FTP port, username, and password.
5. In the app, choose **Upload to Xbox via FTP**, enter those details, and test the connection. Set the base path to the HDD root exposed by your dashboard (the default is `Hdd1:/`; adjust it if your FTP server uses another spelling).
6. Convert. Each output file is staged on the PC and then sent to the console. When finished, rescan the Content path in Aurora/FSD.

## Important safety and limitations

- Use FTP only on a trusted home LAN. Xbox FTP is normally unencrypted. **Do not enable router port forwarding or expose the console's FTP port to the public internet.**
- The helper binds only to `127.0.0.1` (your own computer), not to your LAN. It does not save FTP credentials to disk; they are held in memory only until the helper exits.
- The ISO is never uploaded. Only the generated package files go from the browser through the local helper to the console.
- The helper temporarily stages one output file at a time on the PC. Allow about 163 MiB of free temporary disk space for a typical full-size data part, plus room for the browser and source ISO.
- If conversion or FTP fails partway through, remove the incomplete output from the Xbox before trying again. The existing output files with matching names may be replaced.
- This does not make packages boot on retail/unmodded consoles; Iso2God-style unsigned GODs require a compatible JTAG/RGH setup.

If `Hdd1:/` is not accepted, use your dashboard's FTP configuration or an FTP client to confirm the exact root path, then enter that base path in the app.
