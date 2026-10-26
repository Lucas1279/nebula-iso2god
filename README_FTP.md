# Nebula ISO2GOD — optional FTP upload

This build includes a local Python helper for FTP because a browser on GitHub Pages cannot open raw FTP connections. The helper serves the page at `http://127.0.0.1:8765/` and connects from your computer to your Xbox.

## Start it (Windows, macOS, or Linux)

1. Install Python 3 if it is not already installed.
2. Keep `index.html` and `ftp_helper.py` together in the same folder.
3. Run `python3 ftp_helper.py` (Windows may use `py ftp_helper.py`). Keep the terminal open. The helper opens its local page automatically; otherwise visit `http://127.0.0.1:8765/`.
4. On the Xbox 360, enable the FTP server in Aurora or FreeStyle Dash and note the console's LAN IP, FTP port, username, and password.
5. In the app, enter the FTP details and test the connection. Use the HDD/USB root exposed by your dashboard. `Usb1` is an example that worked on one setup; names vary by console/dashboard.

## Import a .7z archive locally

In the **Convert an ISO** task, choose **Choose .7z archive…** or drop one `.7z` archive into the ISO drop zone. The page lists the archive locally in a Web Worker and extracts only entries ending in `.iso`, `.xiso`, `.xsf`, `.img`, or `.bin`; other archive entries are not extracted. The original archive on your Mac is left unchanged, and no archive/image data is uploaded. The extracted image stays in the browser's Origin Private File System (OPFS) until you choose another import or reset the page; reset/new import removes the temporary extracted copy.

Use a recent Safari, Chrome, or Edge browser on a secure origin (GitHub Pages HTTPS or the local helper at `http://127.0.0.1:8765/`); do not open `index.html` directly as a `file://` URL. The local helper serves the bundled module-worker and WASM files from `vendor/`, which are needed for the browser-only extractor. Keep `vendor/un7z-opfs/` next to `index.html` and `ftp_helper.py`. The browser needs available site storage for the extracted image and memory for the 7z decompressor; large dictionaries/archives can exceed browser limits. Password-protected or damaged archives are not supported. `.zip` is not accepted by this importer. If an archive contains several supported images, they are queued sequentially; the existing multi-ISO workflow requires FTP output.

When deploying the website, keep `vendor/un7z-opfs/` (including its worker, WASM binary, and license) next to `index.html`; the page loads these files locally. No npm install or network service is needed at runtime.

## Convert and send an ISO

Choose **Convert an ISO**, then choose **Upload to Xbox via FTP** in the output options, test the connection, and convert. Each generated GOD package file is staged on the computer and sent to the console. If FTP disconnects during a file, conversion pauses and offers **Retry file & continue**. Reconnect/check the Xbox and LAN, keep the page and helper open, then use that button; completed package files are kept and conversion continues after the failed file succeeds. FTP `STOR` retries the current file from its beginning (it is not byte-offset resume) and replaces any partial remote copy. If you cancel instead, remove the unconfirmed/partial file or package before starting over. Rescan the Content path in Aurora/FSD after the website reports a complete upload.

## Batch-convert multiple ISOs over FTP

In **Convert an ISO**, select or drop several ISO files. Select **Upload to Xbox via FTP**, test the connection, then start the batch. Each ISO is analyzed, converted, and uploaded as its own GOD package before the next ISO starts. Jobs are sequential—not parallel—so each conversion keeps the usual per-game speed and the Xbox/helper handle only one package at a time. Batch output currently requires FTP. A failed FTP file pauses that ISO and offers the same retry action; successful retry continues the current ISO, then the next ISO runs sequentially. If you cancel or the local helper/staged file is no longer available, the batch stops; completed packages stay on the Xbox, and remove any unconfirmed partial file/package before starting over.

The separate XBLA/XBLIG workflow also accepts multiple content files from the selected Title ID/game folder and uploads them one after another, unchanged. It uses the same retry action if the FTP connection fails during a file.

## Send existing XBLA/XBLIG content unchanged

Choose the separate **Upload existing XBLA/XBLIG file(s)** task at the top of the page. Test the FTP connection, then drop the game's **8-character Title ID folder** (such as `58410B1D`) or its parent game folder into the drop zone. The uploader finds files under `000D0000` and derives the Title ID from the folder path—no manual Title ID entry is needed. The equivalent folder picker is also available.

Each selected file is sent without conversion, renaming, or repacking to:

`<FTP base>/Content/0000000000000000/<TitleID>/000D0000/<original filename>`

The helper creates missing folders. A file with the same name in that destination may be overwritten. For this raw XBLA/XBLIG uploader, archive files are not accepted; extract them yourself first. (The separate ISO conversion task has its own browser-only `.7z` importer.) Drop the Title ID/game folder containing `000D0000`, or choose that folder in the folder picker. After the upload reports complete, rescan Aurora.

## Important safety and limitations

- Use FTP only on a trusted home LAN. Xbox FTP is normally unencrypted. Do not enable router port forwarding or expose the console's FTP port to the public internet.
- The helper binds only to `127.0.0.1` (your own computer), not to your LAN. The optional “Remember Xbox IP and username” checkbox stores only those two values in the browser’s local storage on this Mac; the FTP password is never saved. The checkboxes on both task tabs share the same saved values.
- For ISO conversion, the ISO itself is never uploaded; only generated package files are sent to the Xbox.
- The helper stages one file at a time. Ensure temporary disk space is available for the largest file being sent (raw files may be much larger than a single GOD data part).
- The helper allows up to 180 seconds without FTP data before a transfer times out. Wired Ethernet and a stable USB/HDD connection can reduce stalls.
- FTP transfer does not make unsigned GOD packages boot on retail/unmodded consoles; the ISO-to-GOD path requires compatible JTAG/RGH setup.

If the FTP base path is rejected, use your dashboard's FTP configuration or an FTP client to confirm the exact root path, then enter it in the relevant panel.
