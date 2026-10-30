from __future__ import annotations
import base64
import io
import shutil
import tarfile
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent
ONE_FIXED = ROOT / 'Nebula-ISO2GOD-One-File-Fixed.zip'
ONE_PLAIN = ROOT / 'Nebula-ISO2GOD-One-File.zip'
TIMEOUT = ROOT / 'nebula-iso2god-timeout-fix.zip'
WINDOWS = ROOT / 'Nebula-ISO2GOD-Windows-Helper.zip'
FULL = ROOT / 'NebulaISO2GOD-Full-GitHub-Pages-Build.zip'
UPDATE = ROOT / 'NebulaISO2GOD-Website-Download-Update'


def embedded_command_payload() -> bytes:
    tar_bytes = io.BytesIO()
    paths = [ROOT / 'index.html', ROOT / 'ftp_helper.py', ROOT / 'README_FTP.md', ROOT / 'data/disc_catalog.json']
    paths.extend(sorted((ROOT / 'vendor').rglob('*')))
    with tarfile.open(fileobj=tar_bytes, mode='w:gz', format=tarfile.PAX_FORMAT) as tar:
        for path in paths:
            tar.add(path, arcname=path.relative_to(ROOT).as_posix(), recursive=False)
    return tar_bytes.getvalue()


def rebuild_one_file(zip_path: Path, payload: bytes) -> None:
    with zipfile.ZipFile(zip_path, 'r') as old:
        old_info = old.getinfo('Nebula ISO2GOD.command')
        script = old.read('Nebula ISO2GOD.command').decode('utf-8')
    lines = script.splitlines()
    start = next(i for i, line in enumerate(lines) if line.endswith("<<'NEBULA_EMBEDDED_DATA'")) + 1
    end = lines.index('NEBULA_EMBEDDED_DATA', start)
    b64 = base64.b64encode(payload).decode('ascii')
    body = '\n'.join(b64[i:i+76] for i in range(0, len(b64), 76))
    new_script = '\n'.join(lines[:start] + [body] + lines[end:]) + '\n'
    tmp = zip_path.with_suffix('.tmp.zip')
    with zipfile.ZipFile(tmp, 'w', compression=zipfile.ZIP_DEFLATED, compresslevel=9) as out:
        info = zipfile.ZipInfo(old_info.filename, old_info.date_time)
        info.compress_type = zipfile.ZIP_DEFLATED
        info.create_system = old_info.create_system
        info.external_attr = old_info.external_attr
        info.flag_bits = old_info.flag_bits
        info.comment = old_info.comment
        out.writestr(info, new_script.encode('utf-8'))
    tmp.replace(zip_path)


def update_mac_readme(text: str) -> str:
    lines = [line for line in text.splitlines() if not line.startswith('SNES360 ROMs:') and not line.startswith('FTP manager editor:') and not line.startswith('FTP manager drag/drop:')]
    lines.append('FTP manager editor: click the remote `launch.ini` filename to open the built-in UTF-8 editor, or select it and use **Edit launch.ini** in the sticky toolbar above the file listing. Saving overwrites the remote file after a themed confirmation; keep a backup first. The editor is limited to 2 MiB and only edits valid UTF-8 text. FTP manager confirmation, retry, and folder-name dialogs use the site theme.')
    lines.append('FTP manager drag/drop: drag a remote file row onto a folder row to move it within Xbox FTP; selected file rows move together and same-name collisions are refused. For actual desktop drag-out, Chrome/Edge desktop can stage one remote file up to 64 MiB with **Prepare drag-out**, then drag that row to the desktop within 15 minutes. The local helper serves the staged bytes from a short-lived HTTP URL. Safari/Firefox do not reliably export file bytes by page drag, so use **Import selected to computer** there, for larger files, or for batches.')
    lines.append('SNES360 ROMs: copies `.sfc`, `.smc`, `.swc`, and `.fig` ROM data unchanged; a standalone `.7z` can be unpacked locally to supported ROM files. FATX-invalid characters (including `+`) are replaced with hyphens and overlong Xbox destination names are shortened while preserving extensions; Mac source names and file bytes remain untouched. Default FTP target is base `usb1/` plus `emulators/Snes360/Roms`. Make sure SNES360 scans/maps that path; editable presets cover HDD, USB0, and legacy USB0 destinations.')
    return '\n'.join(lines).rstrip() + '\n'


def rebuild_timeout_bundle() -> None:
    with zipfile.ZipFile(TIMEOUT, 'r') as old:
        members = [(info, old.read(info.filename)) for info in old.infolist()]
    tmp = TIMEOUT.with_suffix('.tmp.zip')
    with zipfile.ZipFile(tmp, 'w', compression=zipfile.ZIP_DEFLATED, compresslevel=9) as out:
        catalog_written = False
        for info, data in members:
            name = info.filename
            if name.endswith('/index.html'):
                data = (ROOT / 'index.html').read_bytes()
            elif name.endswith('/data/disc_catalog.json'):
                if catalog_written:
                    continue
                data = (ROOT / 'data/disc_catalog.json').read_bytes()
                catalog_written = True
            elif name.endswith('/ftp_helper.py'):
                data = (ROOT / 'ftp_helper.py').read_bytes()
            elif name.endswith('/README_FTP.md'):
                data = (ROOT / 'README_FTP.md').read_bytes()
            elif name.endswith('/README_MAC.txt'):
                data = update_mac_readme(data.decode('utf-8')).encode('utf-8')
            new_info = zipfile.ZipInfo(name, info.date_time)
            new_info.compress_type = zipfile.ZIP_DEFLATED
            new_info.create_system = info.create_system
            new_info.external_attr = info.external_attr
            new_info.flag_bits = info.flag_bits
            out.writestr(new_info, data)
        if not catalog_written:
            site_prefix = next(info.filename.rsplit('index.html', 1)[0] for info, _ in members if info.filename.endswith('/index.html'))
            out.write(ROOT / 'data/disc_catalog.json', site_prefix + 'data/disc_catalog.json')
    tmp.replace(TIMEOUT)


def rebuild_windows_bundle() -> None:
    """Package the current site/helper with a Windows batch launcher."""
    prefix = 'Nebula ISO2GOD Windows Helper/'
    files = [ROOT / 'index.html', ROOT / 'ftp_helper.py', ROOT / 'README_FTP.md',
             ROOT / 'README_WINDOWS.txt', ROOT / 'Start Nebula ISO2GOD.bat', ROOT / 'data/disc_catalog.json']
    files.extend(sorted((ROOT / 'vendor').rglob('*')))
    with zipfile.ZipFile(WINDOWS, 'w', compression=zipfile.ZIP_DEFLATED, compresslevel=9) as out:
        for path in files:
            if path.is_file():
                out.write(path, prefix + path.relative_to(ROOT).as_posix())


def update_deployment_copy() -> None:
    if not UPDATE.exists():
        UPDATE.mkdir(parents=True)
    for name in ['index.html', 'ftp_helper.py', 'README_FTP.md', 'README.md', 'UPLOAD_TO_GITHUB.txt']:
        src = ROOT / name
        if src.exists():
            shutil.copy2(src, UPDATE / name)
    for name in [ONE_FIXED.name, ONE_PLAIN.name, TIMEOUT.name, WINDOWS.name]:
        shutil.copy2(ROOT / name, UPDATE / name)
    (UPDATE / 'data').mkdir(exist_ok=True)
    shutil.copy2(ROOT / 'data/disc_catalog.json', UPDATE / 'data/disc_catalog.json')
    if (ROOT / 'vendor').exists():
        if (UPDATE / 'vendor').exists(): shutil.rmtree(UPDATE / 'vendor')
        shutil.copytree(ROOT / 'vendor', UPDATE / 'vendor')


def rebuild_full_pages_zip() -> None:
    files = [ROOT / 'index.html', ROOT / 'ftp_helper.py', ROOT / 'README.md', ROOT / 'README_FTP.md', ROOT / 'UPLOAD_TO_GITHUB.txt', ROOT / 'build_disc_catalog.py', ROOT / 'rebuild_bundles.py', ROOT / 'test_disc_catalog.py', ROOT / 'data/disc_catalog.json', ROOT / 'data/disc_catalog_review.md', ROOT / 'data/redump-xbox360-dat.zip', ROOT / 'data/xbox360-gamelist.csv', ONE_FIXED, ONE_PLAIN, TIMEOUT, WINDOWS]
    files.extend(sorted((ROOT / 'vendor').rglob('*')))
    with zipfile.ZipFile(FULL, 'w', compression=zipfile.ZIP_DEFLATED, compresslevel=9) as out:
        for path in files:
            out.write(path, path.relative_to(ROOT).as_posix())


def main() -> None:
    payload = embedded_command_payload()
    rebuild_one_file(ONE_FIXED, payload)
    rebuild_one_file(ONE_PLAIN, payload)
    rebuild_timeout_bundle()
    rebuild_windows_bundle()
    update_deployment_copy()
    rebuild_full_pages_zip()
    print('Rebuilt Mac and Windows helper downloads, deployment copy, and full Pages ZIP.')


if __name__ == '__main__':
    main()
