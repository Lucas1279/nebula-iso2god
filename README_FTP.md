# Nebula ISO2GOD — optional FTP upload

This build includes a local Python helper for FTP because a browser on GitHub Pages cannot open raw FTP connections. The helper serves the page at `http://127.0.0.1:8765/` and connects from your computer to your Xbox.

## Start it (Windows, macOS, or Linux)

1. Install Python 3 if it is not already installed.
2. Keep `index.html` and `ftp_helper.py` together in the same folder.
3. Run `python3 ftp_helper.py` (Windows may use `py ftp_helper.py`). Keep the terminal open. The helper opens its local page automatically; otherwise visit `http://127.0.0.1:8765/`.
4. On the Xbox 360, enable the FTP server in Aurora or FreeStyle Dash and note the console's LAN IP, FTP port, username, and password.
5. In the app, enter the FTP details and test the connection. Use the HDD/USB root exposed by your dashboard. `Usb1` is an example that worked on one setup; names vary by console/dashboard.

## Convert and send an ISO

Choose **Convert an ISO**, then choose **Upload to Xbox via FTP** in the output options, test the connection, and convert. Each generated GOD package file is staged on the computer and sent to the console. Rescan the Content path in Aurora/FSD after the website reports a complete upload.

## Send existing XBLA/XBLIG content unchanged

Choose the separate **Upload existing XBLA/XBLIG file(s)** task at the top of the page. Test the FTP connection, then drop the game's **8-character Title ID folder** (such as `58410B1D`) or its parent game folder into the drop zone. The uploader finds files under `000D0000` and derives the Title ID from the folder path—no manual Title ID entry is needed. The equivalent folder picker is also available.

Each selected file is sent without conversion, renaming, or repacking to:

`<FTP base>/Content/0000000000000000/<TitleID>/000D0000/<original filename>`

The helper creates missing folders. A file with the same name in that destination may be overwritten. Do not drop the outer `.7z` archive; extract it first. Drop the Title ID/game folder containing `000D0000`, or choose that folder in the folder picker. After the upload reports complete, rescan Aurora.

## Important safety and limitations

- Use FTP only on a trusted home LAN. Xbox FTP is normally unencrypted. Do not enable router port forwarding or expose the console's FTP port to the public internet.
- The helper binds only to `127.0.0.1` (your own computer), not to your LAN. FTP credentials are held in memory only until the helper exits.
- For ISO conversion, the ISO itself is never uploaded; only generated package files are sent to the Xbox.
- The helper stages one file at a time. Ensure temporary disk space is available for the largest file being sent (raw files may be much larger than a single GOD data part).
- The helper allows up to 180 seconds without FTP data before a transfer times out. Wired Ethernet and a stable USB/HDD connection can reduce stalls.
- FTP transfer does not make unsigned GOD packages boot on retail/unmodded consoles; the ISO-to-GOD path requires compatible JTAG/RGH setup.

If the FTP base path is rejected, use your dashboard's FTP configuration or an FTP client to confirm the exact root path, then enter it in the relevant panel.
