"""Focused unit tests for the local FTP bridge's safe file-manager helpers."""
import json
import tempfile
import threading
import unittest
from http.server import ThreadingHTTPServer
from pathlib import Path
from unittest.mock import patch
from urllib.request import Request, urlopen

import ftp_helper


class FakeDataSocket:
    def __init__(self, data):
        self.data = data
        self.offset = 0
    def recv(self, size):
        chunk = self.data[self.offset:self.offset + size]
        self.offset += len(chunk)
        return chunk
    def close(self):
        pass


class FakeFTP:
    def __init__(self, tree):
        self.tree = tree
        self.path = []
        self.commands = []

    def pwd(self):
        return "/" + "/".join(self.path)

    def cwd(self, name):
        if name == "..":
            self.path = self.path[:-1]
            return
        if name.startswith("/"):
            self.path = [part for part in name.split("/") if part]
            return
        current = self.tree
        for part in self.path:
            current = current[part]
        if name not in current or not isinstance(current[name], dict):
            raise OSError("not a directory")
        self.path.append(name)

    def mlsd(self):
        current = self.tree
        for part in self.path:
            current = current[part]
        for name, value in list(current.items()):
            yield name, {"type": "dir" if isinstance(value, dict) else "file",
                         "size": str(len(value) if isinstance(value, bytes) else 0)}

    def nlst(self):
        current = self.tree
        for part in self.path:
            current = current[part]
        return list(current)

    def delete(self, name):
        current = self.tree
        for part in self.path:
            current = current[part]
        del current[name]

    def rename(self, old_name, new_path):
        current = self.tree
        for part in self.path:
            current = current[part]
        parts = [part for part in new_path.split("/") if part]
        target_name = parts[-1]
        target = current
        for part in parts[:-1]:
            if part not in target or not isinstance(target[part], dict):
                raise OSError("destination directory not found")
            target = target[part]
        if target_name in target:
            raise ftp_helper.ftplib.error_perm("destination exists")
        target[target_name] = current.pop(old_name)

    def transfercmd(self, command):
        name = command[5:]
        current = self.tree
        for part in self.path:
            current = current[part]
        value = current[name]
        if not isinstance(value, bytes):
            raise OSError("not a file")
        return FakeDataSocket(value)

    def voidcmd(self, command):
        self.commands.append(command)
        return "200 Command okay"

    def voidresp(self):
        return "226 Transfer complete"

    def storbinary(self, command, source, blocksize=8192, callback=None):
        self.voidcmd("TYPE I")
        name = command[5:]
        current = self.tree
        for part in self.path:
            current = current[part]
        payload = bytearray()
        while True:
            block = source.read(blocksize)
            if not block:
                break
            payload.extend(block)
            if callback:
                callback(block)
        current[name] = bytes(payload)
        return "226 Transfer complete"

    def sendcmd(self, command):
        raise ftp_helper.ftplib.error_perm("AVBL unsupported")

    def mkd(self, name):
        current = self.tree
        for part in self.path:
            current = current[part]
        if name in current:
            raise ftp_helper.ftplib.error_perm("already exists")
        current[name] = {}

    def rmd(self, name):
        current = self.tree
        for part in self.path:
            current = current[part]
        if current[name]:
            raise OSError("directory not empty")
        del current[name]


class FTPHelperTests(unittest.TestCase):
    def test_path_validation_rejects_traversal_and_separators(self):
        self.assertEqual(ftp_helper.clean_segments(["Games", "RPG"]), ["Games", "RPG"])
        self.assertEqual(ftp_helper.clean_segments([], allow_empty=True), [])
        for segments in ([".."], ["a/b"], ["a\\b"], ["bad\x00name"]):
            with self.subTest(segments=segments), self.assertRaises(ValueError):
                ftp_helper.clean_segments(segments)
        with self.assertRaises(ValueError):
            ftp_helper.clean_name("../save.dat")

    def test_parse_optional_ftp_avbl_responses(self):
        self.assertEqual(ftp_helper.parse_ftp_available_bytes("213 123456789"), 123456789)
        self.assertEqual(ftp_helper.parse_ftp_available_bytes("213 1,234,567 bytes available"), 1234567)
        self.assertIsNone(ftp_helper.parse_ftp_available_bytes("502 AVBL unsupported"))
        self.assertIsNone(ftp_helper.parse_ftp_available_bytes("213 not reported"))

    def test_parse_unix_and_dos_list_formats(self):
        unix = ftp_helper.parse_ftp_list_line("drwxr-xr-x 2 xbox xbox 4096 Jan 12 12:45 Saves")
        self.assertEqual((unix["name"], unix["type"], unix["size"]), ("Saves", "dir", 4096))
        dos = ftp_helper.parse_ftp_list_line("01-12-2026  12:45PM       <DIR>          Saves")
        self.assertEqual((dos["name"], dos["type"]), ("Saves", "dir"))
        file_entry = ftp_helper.parse_ftp_list_line("01-12-2026  12:45PM             42 save.dat")
        self.assertEqual((file_entry["name"], file_entry["type"], file_entry["size"]), ("save.dat", "file", 42))
        self.assertIsNone(ftp_helper.parse_ftp_list_line("unrecognized listing output"))

    def test_mlsd_listing_is_normalized(self):
        ftp = FakeFTP({"folder": {}, "game.iso": b"1234"})
        entries = ftp_helper.ftp_list_entries(ftp)
        self.assertEqual({(e["name"], e["type"], e["size"]) for e in entries},
                         {("folder", "dir", 0), ("game.iso", "file", 4)})

    def test_list_fallback_and_nlst_probe(self):
        class ListFTP(FakeFTP):
            def mlsd(self):
                raise ftp_helper.ftplib.error_perm("MLSD unsupported")
            def dir(self, callback):
                callback("drwxr-xr-x 2 xbox xbox 4096 Jan 12 12:45 Saves")
                callback("-rw-r--r-- 1 xbox xbox 77 Jan 12 12:45 notes.txt")
        entries = ftp_helper.ftp_list_entries(ListFTP({"Saves": {}, "notes.txt": b"x" * 77}))
        self.assertEqual({(e["name"], e["type"], e["size"]) for e in entries},
                         {("Saves", "dir", 4096), ("notes.txt", "file", 77)})

        class NLSTFTP(ListFTP):
            def dir(self, callback): callback("listing format not recognized")
            def nlst(self): return ["Saves", "notes.txt"]
            def size(self, name): return 77 if name == "notes.txt" else None
        entries = ftp_helper.ftp_list_entries(NLSTFTP({"Saves": {}, "notes.txt": b"x" * 77}))
        self.assertEqual({(e["name"], e["type"]) for e in entries}, {("Saves", "dir"), ("notes.txt", "file")})

    def test_startup_cleanup_removes_abandoned_upload_and_download_stages(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            upload = Path(temp_dir) / "nebula-ftp-old.part"
            download = Path(temp_dir) / "nebula-download-old.part"
            drag_export = Path(temp_dir) / "nebula-drag-export-old.part"
            unrelated = Path(temp_dir) / "keep-me.txt"
            upload.write_bytes(b"upload")
            download.write_bytes(b"download")
            drag_export.write_bytes(b"drag export")
            unrelated.write_text("keep")
            with patch.object(ftp_helper.tempfile, "gettempdir", return_value=temp_dir):
                ftp_helper.cleanup_stale_staging_files()
            self.assertFalse(upload.exists())
            self.assertFalse(download.exists())
            self.assertFalse(drag_export.exists())
            self.assertTrue(unrelated.exists())

    def test_recursive_delete_removes_files_and_nested_folders(self):
        tree = {"Games": {"RPG": {"save.dat": b"save", "nested": {"config.ini": b"cfg"}}, "other.iso": b"iso"}}
        ftp = FakeFTP(tree)
        ftp.cwd("Games")
        ftp_helper.ftp_remove_tree(ftp, "RPG")
        self.assertEqual(tree, {"Games": {"other.iso": b"iso"}})
        self.assertEqual(ftp.pwd(), "/Games")


class FTPRouteTests(unittest.TestCase):
    def setUp(self):
        self.game_save_bytes = bytes([0, 1]) + b"save" + bytes([13, 10, 255, 128, 0]) + b"binary"
        self.tree = {"Saves": {"slot.dat": b"save", "ALIAS_SKATER": self.game_save_bytes, "Archive": {}}}
        self.previous_config = ftp_helper.CONFIG
        self.previous_local_sessions = ftp_helper.LOCAL_OUTPUT_SESSIONS
        self.previous_local_files = ftp_helper.LOCAL_OUTPUT_FILES
        self.previous_download_tickets = ftp_helper.DOWNLOAD_TICKETS
        ftp_helper.LOCAL_OUTPUT_SESSIONS = {}
        ftp_helper.LOCAL_OUTPUT_FILES = {}
        ftp_helper.DOWNLOAD_TICKETS = {}
        ftp_helper.CONFIG = {"host": "xbox", "port": 21, "user": "x", "password": "", "basePath": "/"}
        self.ftp_instances = []
        def make_ftp(_cfg):
            ftp = FakeFTP(self.tree)
            self.ftp_instances.append(ftp)
            return ftp
        self.login_patch = patch.object(ftp_helper, "ftp_login", side_effect=make_ftp)
        self.login_patch.start()
        self.server = ThreadingHTTPServer(("127.0.0.1", 0), ftp_helper.Handler)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.url = "http://127.0.0.1:%d" % self.server.server_port

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=2)
        self.login_patch.stop()
        for item in ftp_helper.LOCAL_OUTPUT_FILES.values():
            try: Path(item["tmp"]).unlink()
            except OSError: pass
        ftp_helper.LOCAL_OUTPUT_FILES = self.previous_local_files
        ftp_helper.LOCAL_OUTPUT_SESSIONS = self.previous_local_sessions
        ftp_helper.DOWNLOAD_TICKETS = self.previous_download_tickets
        ftp_helper.CONFIG = self.previous_config

    def post(self, path, payload):
        request = Request(self.url + path, data=json.dumps(payload).encode(), method="POST",
                          headers={"Content-Type": "application/json", "X-Nebula-Token": ftp_helper.TOKEN})
        with urlopen(request, timeout=3) as response:
            return json.loads(response.read())

    def post_raw(self, path, payload):
        request = Request(self.url + path, data=payload, method="POST",
                          headers={"Content-Type": "application/octet-stream", "X-Nebula-Token": ftp_helper.TOKEN})
        with urlopen(request, timeout=3) as response:
            return json.loads(response.read())

    def test_connect_route_preserves_exact_start_path(self):
        seen = []

        class CaptureFTP:
            def cwd(self, path):
                seen.append(path)
            def pwd(self):
                return "/" + seen[-1]
            def quit(self):
                pass

        with patch.object(ftp_helper, "ftp_login", side_effect=lambda cfg: CaptureFTP()):
            result = self.post("/api/connect", {
                "host": "xbox", "port": 21, "user": "x", "password": "", "basePath": "usb1"
            })
        self.assertEqual(seen, ["usb1"])
        self.assertEqual(result["cwd"], "/usb1")
        self.assertEqual(ftp_helper.CONFIG["basePath"], "usb1")

    def test_storage_route_reports_optional_free_bytes_or_unavailable(self):
        commands = []

        class AVBLFTP(FakeFTP):
            def sendcmd(self, command):
                commands.append(command)
                if command == "AVBL":
                    raise ftp_helper.ftplib.error_perm("AVBL requires a path")
                if command == "AVBL /Saves":
                    return "213 987654321 bytes available"
                raise ftp_helper.ftplib.error_perm("unsupported")

        with patch.object(ftp_helper, "ftp_login", side_effect=lambda cfg: AVBLFTP(self.tree)):
            result = self.post("/api/fs/storage", {"segments": ["Saves"]})
        self.assertEqual(result["availableBytes"], 987654321)
        self.assertEqual(commands, ["AVBL", "AVBL /Saves"])

        unavailable = self.post("/api/fs/storage", {"segments": []})
        self.assertIsNone(unavailable["availableBytes"])

    def test_list_create_and_recursive_delete_routes(self):
        listing = self.post("/api/fs/list", {"segments": []})
        self.assertEqual(listing["cwd"], "/")
        self.assertEqual([(e["name"], e["type"]) for e in listing["entries"]], [("Saves", "dir")])

        created = self.post("/api/fs/mkdir", {"segments": [], "name": "Screenshots"})
        self.assertTrue(created["created"])
        self.assertIn("Screenshots", self.tree)
        existing = self.post("/api/fs/mkdir", {"segments": [], "name": "Screenshots"})
        self.assertFalse(existing["created"])

        deleted = self.post("/api/fs/delete", {"segments": ["Saves"], "recursive": True})
        self.assertEqual(deleted["type"], "dir")
        self.assertEqual(self.tree, {"Screenshots": {}})

    def test_download_route_streams_selected_remote_file(self):
        request = Request(self.url + "/api/fs/download", data=json.dumps({"segments": ["Saves", "slot.dat"]}).encode(), method="POST",
                          headers={"Content-Type": "application/json", "X-Nebula-Token": ftp_helper.TOKEN})
        with urlopen(request, timeout=3) as response:
            self.assertEqual(response.read(), b"save")
            self.assertIn('filename="slot.dat"', response.headers["Content-Disposition"])
            self.assertEqual(response.headers["Content-Type"], "application/octet-stream")

    def test_extensionless_game_save_download_preserves_binary_bytes_and_filename(self):
        ticket = self.post("/api/fs/download-ticket", {"segments": ["Saves", "ALIAS_SKATER"]})
        self.assertEqual(ticket["name"], "ALIAS_SKATER")
        with urlopen(self.url + ticket["url"], timeout=3) as response:
            self.assertEqual(response.read(), self.game_save_bytes)
            self.assertEqual(response.headers["Content-Type"], "application/octet-stream")
            self.assertIn('filename="ALIAS_SKATER"', response.headers["Content-Disposition"])
        self.assertIn("TYPE I", self.ftp_instances[-1].commands)
        with self.assertRaises(Exception):
            urlopen(self.url + ticket["url"], timeout=3)

    def test_extensionless_game_save_upload_preserves_binary_bytes(self):
        begun = self.post("/api/file/begin", {
            "segments": ["Saves", "CFOTO_SKATER"], "size": len(self.game_save_bytes)
        })
        self.post_raw("/api/file/chunk?id=" + begun["id"], self.game_save_bytes)
        result = self.post("/api/file/finish", {"id": begun["id"]})
        self.assertEqual(result["bytes"], len(self.game_save_bytes))
        self.assertEqual(self.tree["Saves"]["CFOTO_SKATER"], self.game_save_bytes)
        self.assertIn("TYPE I", self.ftp_instances[-1].commands)
        self.post("/api/file/ack", {"id": begun["id"]})
        self.assertNotIn(begun["id"], ftp_helper.ACTIVE)

    def test_move_route_moves_remote_file_into_child_folder_without_overwriting(self):
        moved = self.post("/api/fs/move", {
            "sourceSegments": ["Saves", "slot.dat"],
            "destinationSegments": ["Saves", "Archive", "slot.dat"],
        })
        self.assertEqual(moved["name"], "slot.dat")
        self.assertNotIn("slot.dat", self.tree["Saves"])
        self.assertEqual(self.tree["Saves"]["Archive"]["slot.dat"], b"save")

        self.tree["Saves"]["other.dat"] = b"source"
        self.tree["Saves"]["Archive"]["OTHER.DAT"] = b"keep"
        request = Request(self.url + "/api/fs/move", data=json.dumps({
            "sourceSegments": ["Saves", "other.dat"],
            "destinationSegments": ["Saves", "Archive", "other.dat"],
        }).encode(), method="POST", headers={"Content-Type": "application/json", "X-Nebula-Token": ftp_helper.TOKEN})
        with self.assertRaises(Exception):
            urlopen(request, timeout=3)
        self.assertEqual(self.tree["Saves"]["other.dat"], b"source")
        self.assertEqual(self.tree["Saves"]["Archive"]["OTHER.DAT"], b"keep")
        self.assertNotIn("other.dat", self.tree["Saves"]["Archive"])

    def test_move_route_rejects_paths_outside_current_folder_tree(self):
        request = Request(self.url + "/api/fs/move", data=json.dumps({
            "sourceSegments": ["Saves", "slot.dat"],
            "destinationSegments": ["Other", "slot.dat"],
        }).encode(), method="POST", headers={"Content-Type": "application/json", "X-Nebula-Token": ftp_helper.TOKEN})
        with self.assertRaises(Exception):
            urlopen(request, timeout=3)
        self.assertIn("slot.dat", self.tree["Saves"])

    def test_rename_route_renames_remote_file_and_refuses_collisions(self):
        renamed = self.post("/api/fs/rename", {"segments": ["Saves", "slot.dat"], "newName": "slot-final.dat"})
        self.assertTrue(renamed["renamed"])
        self.assertNotIn("slot.dat", self.tree["Saves"])
        self.assertEqual(self.tree["Saves"]["slot-final.dat"], b"save")

        self.tree["Saves"]["taken.dat"] = b"keep"
        request = Request(self.url + "/api/fs/rename", data=json.dumps({
            "segments": ["Saves", "slot-final.dat"], "newName": "TAKEN.DAT"
        }).encode(), method="POST", headers={"Content-Type": "application/json", "X-Nebula-Token": ftp_helper.TOKEN})
        with self.assertRaises(Exception):
            urlopen(request, timeout=3)
        self.assertEqual(self.tree["Saves"]["slot-final.dat"], b"save")
        self.assertEqual(self.tree["Saves"]["taken.dat"], b"keep")

    def test_download_route_enforces_optional_size_limit(self):
        request = Request(self.url + "/api/fs/download", data=json.dumps({
            "segments": ["Saves", "slot.dat"], "maxBytes": 3
        }).encode(), method="POST", headers={"Content-Type": "application/json", "X-Nebula-Token": ftp_helper.TOKEN})
        with self.assertRaises(Exception):
            urlopen(request, timeout=3)

    def test_token_route_advertises_macos_folder_picker_support(self):
        with patch.object(ftp_helper, "mac_local_folder_picker_available", return_value=True):
            request = Request(self.url + "/api/token")
            with urlopen(request, timeout=3) as response:
                token_info = json.loads(response.read())
        self.assertEqual(token_info["token"], ftp_helper.TOKEN)
        self.assertTrue(token_info["localFolderPickerAvailable"])

    def test_local_native_folder_output_picks_streams_checks_and_removes_files(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            with patch.object(ftp_helper, "choose_local_output_folder", return_value=Path(temp_dir)):
                picked = self.post("/api/local-output/pick", {})
            self.assertFalse(picked["cancelled"])
            self.assertEqual(picked["name"], Path(temp_dir).name)
            session_id = picked["sessionId"]
            segments = ["Content", "0000000000000000", "12345678", "00007000", "Game.data", "Data0000"]
            begin = self.post("/api/local-output/file/begin", {
                "sessionId": session_id, "segments": segments, "size": 8
            })
            self.post_raw("/api/local-output/file/chunk?id=" + begin["id"], b"GOD-")
            self.post_raw("/api/local-output/file/chunk?id=" + begin["id"], b"data")
            finished = self.post("/api/local-output/file/finish", {"id": begin["id"]})
            self.assertEqual(finished["bytes"], 8)
            target = Path(temp_dir).joinpath(*segments)
            self.assertEqual(target.read_bytes(), b"GOD-data")
            checked = self.post("/api/local-output/check", {
                "sessionId": session_id, "paths": [segments, ["Content", "missing.bin"]]
            })
            self.assertEqual(checked["exists"], [True, False])
            removed = self.post("/api/local-output/remove", {
                "sessionId": session_id, "segments": segments, "recursive": False
            })
            self.assertTrue(removed["removed"])
            self.assertFalse(target.exists())
            self.post("/api/local-output/release", {"sessionId": session_id})

    def test_local_output_refuses_symlink_escape_from_selected_root(self):
        with tempfile.TemporaryDirectory() as temp_dir, tempfile.TemporaryDirectory() as outside_dir:
            root = Path(temp_dir)
            (root / "escape").symlink_to(outside_dir, target_is_directory=True)
            with patch.object(ftp_helper, "choose_local_output_folder", return_value=root):
                session_id = self.post("/api/local-output/pick", {})["sessionId"]
            request = Request(self.url + "/api/local-output/file/begin", data=json.dumps({
                "sessionId": session_id, "segments": ["escape", "should-not-exist.bin"], "size": 1
            }).encode(), method="POST", headers={"Content-Type": "application/json", "X-Nebula-Token": ftp_helper.TOKEN})
            with self.assertRaises(Exception):
                urlopen(request, timeout=3)
            self.assertFalse((Path(outside_dir) / "should-not-exist.bin").exists())
            self.post("/api/local-output/release", {"sessionId": session_id})

    def test_local_output_rejects_unsafe_paths_and_incomplete_files(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            with patch.object(ftp_helper, "choose_local_output_folder", return_value=Path(temp_dir)):
                session_id = self.post("/api/local-output/pick", {})["sessionId"]
            bad = Request(self.url + "/api/local-output/file/begin", data=json.dumps({
                "sessionId": session_id, "segments": ["..", "outside.bin"], "size": 1
            }).encode(), method="POST", headers={"Content-Type": "application/json", "X-Nebula-Token": ftp_helper.TOKEN})
            with self.assertRaises(Exception):
                urlopen(bad, timeout=3)
            begin = self.post("/api/local-output/file/begin", {
                "sessionId": session_id, "segments": ["partial.bin"], "size": 3
            })
            self.post_raw("/api/local-output/file/chunk?id=" + begin["id"], b"x")
            incomplete = Request(self.url + "/api/local-output/file/finish", data=json.dumps({"id": begin["id"]}).encode(),
                                 method="POST", headers={"Content-Type": "application/json", "X-Nebula-Token": ftp_helper.TOKEN})
            with self.assertRaises(Exception):
                urlopen(incomplete, timeout=3)
            self.post("/api/local-output/file/abort", {"id": begin["id"]})
            self.assertFalse((Path(temp_dir) / "partial.bin").exists())
            self.post("/api/local-output/release", {"sessionId": session_id})

    def test_drag_export_stages_and_serves_exact_file_bytes_without_auth_header(self):
        payload = b"Aurora launch settings" + bytes([13, 10]) + b"DashPath = Hdd1:/" + bytes([0, 255])
        begun = self.post("/api/drag-export/begin", {"name": "launch.ini", "size": len(payload)})
        ident = begun["id"]
        try:
            split = len(payload) // 2
            self.post_raw("/api/drag-export/chunk?id=" + ident, payload[:split])
            self.post_raw("/api/drag-export/chunk?id=" + ident, payload[split:])
            ready = self.post("/api/drag-export/finish", {"id": ident})
            self.assertIn("expiresIn", ready)
            head = Request(self.url + ready["url"], method="HEAD")
            with urlopen(head, timeout=3) as response:
                self.assertEqual(response.headers["Content-Length"], str(len(payload)))
                self.assertEqual(response.read(), b"")
            request = Request(self.url + ready["url"], method="GET")
            with urlopen(request, timeout=3) as response:
                self.assertEqual(response.read(), payload)
                self.assertEqual(response.headers["Content-Length"], str(len(payload)))
                self.assertIn('filename="launch.ini"', response.headers["Content-Disposition"])
        finally:
            self.post("/api/drag-export/abort", {"id": ident})

    def test_drag_export_rejects_files_over_size_limit(self):
        request = Request(self.url + "/api/drag-export/begin", data=json.dumps({
            "name": "too-big.bin", "size": ftp_helper.DRAG_EXPORT_MAX_BYTES + 1
        }).encode(), method="POST", headers={"Content-Type": "application/json", "X-Nebula-Token": ftp_helper.TOKEN})
        with self.assertRaises(Exception):
            urlopen(request, timeout=3)

    def test_delete_route_refuses_root_and_invalid_path(self):
        for payload in ({"segments": []}, {"segments": ["..", "Saves"]}):
            request = Request(self.url + "/api/fs/delete", data=json.dumps(payload).encode(), method="POST",
                              headers={"Content-Type": "application/json", "X-Nebula-Token": ftp_helper.TOKEN})
            with self.assertRaises(Exception):
                urlopen(request, timeout=3)


if __name__ == "__main__":
    unittest.main()
