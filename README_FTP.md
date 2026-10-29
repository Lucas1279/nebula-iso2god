# Nebula ISO2GOD — optional FTP upload

This build includes a local Python helper for FTP because a browser on GitHub Pages cannot open raw FTP connections. The helper serves the page at `http://127.0.0.1:8765/` and connects from your computer to your Xbox.

## Start it (Windows, macOS, or Linux)

1. Install Python 3 if it is not already installed.
2. Keep `index.html` and `ftp_helper.py` together in the same folder.
3. Run `python3 ftp_helper.py` (Windows may use `py ftp_helper.py`). Keep the terminal open. The helper opens its local page automatically; otherwise visit `http://127.0.0.1:8765/`.
4. On the Xbox 360, enable the FTP server in Aurora or FreeStyle Dash and note the console's LAN IP, FTP port, username, and password.
5. In the app, enter the FTP details and test the connection. Use the HDD/USB root exposed by your dashboard. `Usb1` is an example that worked on one setup; names vary by console/dashboard.

## Import a .7z archive locally

In the **Convert an ISO** task, choose **Choose .7z archive…** or drop one `.7z` archive into the ISO drop zone. The page lists the archive locally in a Web Worker and extracts only entries ending in `.iso`, `.xiso`, `.xsf`, `.img`, or `.bin`; other archive entries are not extracted. The original archive on your Mac is left unchanged, and no archive/image data is uploaded. The extracted image stays in the browser's Origin Private File System (OPFS) while it is needed for conversion and any FTP retry. After a successful conversion (or successful batch), the app removes the temporary extraction automatically. It also cleans up on a new import, reset, failure, or page exit; the original .7z archive is unchanged.

Use a recent Safari, Chrome, or Edge browser on a secure origin (GitHub Pages HTTPS or the local helper at `http://127.0.0.1:8765/`); do not open `index.html` directly as a `file://` URL. The local helper serves the bundled module-worker and WASM files from `vendor/`, which are needed for the browser-only extractor. Keep `vendor/un7z-opfs/` next to `index.html` and `ftp_helper.py`. The browser needs available site storage for the extracted image and memory for the 7z decompressor; large dictionaries/archives can exceed browser limits. Password-protected or damaged archives are not supported. `.zip` is not accepted by this importer. If an archive contains several supported images, they are queued sequentially; the existing multi-ISO workflow requires FTP output.

When deploying the website, keep `vendor/un7z-opfs/` (including its worker, WASM binary, and license) next to `index.html`; the page loads these files locally. No npm install or network service is needed at runtime.

## Browse and manage files on the Xbox

Open **Xbox FTP file manager** at the top of the locally served app. Its **Download Mac one-tap helper** button stays visible whenever the FTP manager page is open; use it to download the updated fixed Mac launcher ZIP, unzip it, and open `Nebula ISO2GOD.command` (Python 3 is required). Connect with the console's FTP host, port, username, password, and a starting drive/path exposed by Aurora or FreeStyle Dash (for example `Hdd1:/` or `Usb0:/`). The manager lists the folders and files below that starting path; open folders and use **Back**, **Forward**, breadcrumbs, or **Up** to navigate. The history arrows appear immediately above the file listing. The static GitHub Pages site cannot browse FTP by itself—the local helper must be running and the page must be opened from its loopback address.

Use **Upload files**, **Upload folder**, or drag PC files/folders into the dashed upload area. You can also drop onto an individual remote folder row to upload into that folder. Uploads preserve names and relative folder structure; a remote file with the same path may be replaced. To copy files from the Xbox to your Mac, open the remote folder, select one or more files, then choose **Import selected to computer**; the helper streams them directly to the browser without making an extra disk staging copy. The browser saves them to its Downloads location and may ask permission for multiple downloads. Open folders to reach files—folder downloads as a ZIP are not supported. **New folder** creates a directory at the current location. Select files/folders and choose **Delete selected** to remove them. Deleting a folder is recursive and permanent; the manager deliberately does not allow deleting the configured starting/root folder. The helper validates path segments and rejects links or unknown items during recursive deletion, but use care around saves and system files.

The **Use for ISO → GOD / XBLA / PS1** shortcuts set the selected tool's FTP destination to the currently viewed folder and transfer the active helper connection to that tool. The ISO/XBLA tools create their normal `Content/…` structure below the chosen base; PS1 uploads go to that folder unless a subfolder is selected. Reconnect in the manager when returning to browse, because the helper uses one active FTP connection configuration at a time.

FTP is usually unencrypted. Use this only on a trusted local network. Never forward the Xbox FTP port from your router or expose it to the internet. The helper itself remains loopback-only on the Mac; the FTP connection from the helper to the Xbox travels over your LAN.

## Convert and send an ISO

Choose **Convert an ISO**, then choose **Upload to Xbox via FTP** in the output options, test the connection, and convert. Each generated GOD package file is staged on the computer and sent to the console. If FTP disconnects during a file, conversion pauses and offers **Retry file & continue**. Reconnect/check the Xbox and LAN, keep the page and helper open, then use that button; completed package files are kept and conversion continues after the failed file succeeds. FTP `STOR` retries the current file from its beginning (it is not byte-offset resume) and replaces any partial remote copy. If you cancel instead, remove the unconfirmed/partial file or package before starting over. Rescan the Content path in Aurora/FSD after the website reports a complete upload.

## Batch-convert multiple ISOs over FTP

In **Convert an ISO**, select or drop several ISO files. Select **Upload to Xbox via FTP**, test the connection, then start the batch. Each ISO is analyzed, converted, and uploaded as its own GOD package before the next ISO starts. Jobs are sequential—not parallel—so each conversion keeps the usual per-game speed and the Xbox/helper handle only one package at a time. Batch output currently requires FTP. A failed FTP file pauses that ISO and offers the same retry action; successful retry continues the current ISO, then the next ISO runs sequentially. If you cancel or the local helper/staged file is no longer available, the batch stops; completed packages stay on the Xbox, and remove any unconfirmed partial file/package before starting over.

The separate XBLA/XBLIG workflow accepts multiple content files from the selected Title ID/game folder and uploads them one after another, unchanged. During raw uploads, the overall bar tracks aggregate bytes across the entire selection while the separate blue bar and filename/bytes/speed line track the current Xbox file. It uses the same retry action if the FTP connection fails during a file.

## Send existing XBLA/XBLIG content unchanged

Choose the separate **Upload existing XBLA/XBLIG file(s)** task at the top of the page. First unzip the XBLA archive on your Mac. Then drop/select the game's **8-character Title ID folder** (such as `584111FF`) or its parent game folder; do not select the outer archive, only the `000D0000` folder, or an individual content file. The uploader finds files directly inside the matching `<TitleID>/000D0000/` folder (for example `Quantum Conundrum (World) (XBLA)/584111FF/000D0000/<content file>`) and detects the Title ID automatically.

Each selected file is sent without conversion, renaming, or repacking to:

`<FTP base>/Content/0000000000000000/<TitleID>/000D0000/<original filename>`

The helper creates missing folders. A file with the same name in that destination may be overwritten. Use the folder picker or drag the extracted Title ID/game folder; multiple files are queued and sent one at a time. During upload, the overall job bar tracks aggregate bytes across the selection, while the separate blue bar and filename/bytes/speed line track the current Xbox file. If FTP fails, keep this page, helper, and extracted source files available while you use **Retry file & continue**. After the upload reports complete, rescan Aurora.

## Merge PS1 multi-BIN games for PCSXR360

Choose **PS1 BIN merger for PCSXR360**, then select or drop an extracted PS1 game folder containing one `.cue` and every `.bin` track it references. To send the result directly to the console, choose **Upload to Xbox via FTP**, enter the dashboard FTP details, and test the connection. The base path is the HDD/USB root exposed by the dashboard. The separate Xbox folder field is optional: leave it blank to upload into that base path, or enter the folder PCSXR360 browses for games (for example, `Emulators/PCSXR360/games`). Missing folders are created automatically. Per-game subfolders are also optional.

Each disc is merged locally first. The helper stages one finished file at a time on the computer, then sends the merged `.bin`, its same-named `.cue`, and an optional matching `.sbi` to the Xbox. Keep each `.bin` and `.cue` together with exactly matching names. In PCSXR360, select the `.bin`; the emulator finds the matching `.cue` automatically for track/CD-audio information. Multi-disc games remain separate pairs and should be swapped with the emulator's disc-eject flow. The source folder is never modified. Merging is lossless and does not compress the game; only raw 2352-byte-sector BIN/CUE images are accepted for PCSXR360.

## Important safety and limitations

- Use FTP only on a trusted home LAN. Xbox FTP is normally unencrypted. Do not enable router port forwarding or expose the console's FTP port to the public internet.
- The helper binds only to `127.0.0.1` (your own computer), not to your LAN. The optional “Remember Xbox IP and username” checkbox stores only those two values in the browser’s local storage on this Mac; the FTP password is never saved. The checkboxes on the ISO, XBLA, PS1, and FTP manager panels share the same saved values.
- For ISO conversion, the ISO itself is never uploaded; only generated package files are sent to the Xbox.
- The helper stages one file at a time. Ensure temporary disk space is available for the largest file being sent (raw files may be much larger than a single GOD data part). A failed FTP file remains staged while Retry is available; success, cancel, or normal helper shutdown removes it, and the next helper launch sweeps abandoned staging files from a prior crash.
- The helper allows up to 180 seconds without FTP data before a transfer times out. Wired Ethernet and a stable USB/HDD connection can reduce stalls.
- FTP transfer does not make unsigned GOD packages boot on retail/unmodded consoles; the ISO-to-GOD path requires compatible JTAG/RGH setup.

If the FTP base path is rejected, use your dashboard's FTP configuration or an FTP client to confirm the exact root path, then enter it in the relevant panel.
