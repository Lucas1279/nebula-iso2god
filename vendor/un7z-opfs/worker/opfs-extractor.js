/*
 * Browser-only 7z import worker for Nebula ISO2GOD.
 * Based on un7z-opfs 1.0.2 (https://github.com/caiiiycuk/un7z-opfs),
 * Copyright (C) 1999-2015 Igor Pavlov; see ../License.txt.
 * This worker mounts the selected File as a read-only, seekable virtual file
 * (so the archive is read in slices, not copied wholesale into WASM memory),
 * and extracts only ISO/XISO/XSF/IMG/BIN entries into OPFS.
 */
import SevenZipFactory from '../runtime/7zz.js';

const MOUNT = '/opfs-out';
const INPUT_MOUNT = '/input';
const ARCHIVE_PATH = INPUT_MOUNT + '/archive.7z';
const ARCHIVE_ENTRY_NAME = 'archive.7z';
const IMAGE_EXTENSIONS = /\.(?:iso|xiso|xsf|img|bin)$/i;

export function makeBlobInputFs(FS, blob) {
  const S_IFDIR = 0o040000;
  const S_IFREG = 0o100000;
  const DIR_MODE = S_IFDIR | 0o555;
  const FILE_MODE = S_IFREG | 0o444;
  const reader = (typeof FileReaderSync === 'function') ? new FileReaderSync() : null;
  // 7-Zip often issues many small sequential reads. Read each 1 MiB File slice
  // once, then serve smaller Emscripten reads from this bounded per-stream cache.
  const READ_AHEAD_BYTES = 1024 * 1024;
  let rootNode = null;

  const nodeOps = {
    getattr(node) {
      const isDir = (node.mode & 0o170000) === S_IFDIR;
      const size = isDir ? 0 : Number(blob.size || 0);
      const date = new Date(blob.lastModified || 0);
      return {
        dev: 1, ino: node.id, mode: node.mode, nlink: 1, uid: 0, gid: 0,
        rdev: 0, size, atime: date, mtime: date, ctime: date,
        blksize: 4096, blocks: Math.ceil(size / 4096),
      };
    },
    lookup(parent, name) {
      if (parent === rootNode && name === ARCHIVE_ENTRY_NAME) {
        const node = FS.createNode(parent, name, FILE_MODE, 0);
        node.blobFile = blob;
        node.node_ops = nodeOps;
        node.stream_ops = streamOps;
        return node;
      }
      throw new FS.ErrnoError(2);
    },
    readdir(node) {
      return node === rootNode ? ['.', '..', ARCHIVE_ENTRY_NAME] : ['.', '..'];
    },
    mknod() { throw new FS.ErrnoError(30); },
    setattr() { throw new FS.ErrnoError(30); },
  };

  const streamOps = {
    open(stream) {
      if (!stream.node.blobFile) throw new FS.ErrnoError(5);
      stream.blobFile = stream.node.blobFile;
      stream.readCacheStart = -1;
      stream.readCache = null;
    },
    close(stream) {
      stream.readCache = null;
      stream.blobFile = null;
    },
    read(stream, buffer, offset, length, position) {
      if (!reader) throw new Error('This browser cannot read 7z archives in a worker. Use a recent Chrome or Edge browser.');
      const file = stream.blobFile;
      let cursor = Math.max(0, Number(position) || 0);
      if (cursor >= file.size || length <= 0) return 0;
      let copied = 0;
      while (copied < length && cursor < file.size) {
        const cacheEnd = stream.readCacheStart + (stream.readCache?.length || 0);
        if (!stream.readCache || cursor < stream.readCacheStart || cursor >= cacheEnd) {
          stream.readCacheStart = Math.floor(cursor / READ_AHEAD_BYTES) * READ_AHEAD_BYTES;
          const end = Math.min(file.size, stream.readCacheStart + READ_AHEAD_BYTES);
          stream.readCache = new Uint8Array(reader.readAsArrayBuffer(file.slice(stream.readCacheStart, end)));
        }
        const cacheOffset = cursor - stream.readCacheStart;
        const count = Math.min(length - copied, stream.readCache.length - cacheOffset);
        if (count <= 0) break;
        buffer.set(stream.readCache.subarray(cacheOffset, cacheOffset + count), offset + copied);
        copied += count;
        cursor += count;
      }
      return copied;
    },
    llseek(stream, offset, whence) {
      let position = offset;
      if (whence === 1) position += stream.position;
      else if (whence === 2) position += stream.blobFile.size;
      if (position < 0) throw new FS.ErrnoError(22);
      return position;
    },
  };

  return {
    mount(mount) {
      rootNode = FS.createNode(null, mount.mountpoint, DIR_MODE, 0);
      rootNode.node_ops = nodeOps;
      rootNode.stream_ops = streamOps;
      return rootNode;
    },
  };
}

export function parseArchiveEntries(lines) {
  const entries = [];
  let current = {};
  function flush() {
    const path = current.Path;
    if (path && path !== ARCHIVE_PATH) {
      const attrs = (current.Attributes || '').trim();
      const isDir = current.Folder === '+' || attrs.startsWith('D');
      const size = Number.parseInt(current.Size, 10);
      const normalized = String(path).replace(/\\/g, '/');
      const safe = normalized && !normalized.startsWith('/') && !/^[A-Za-z]:\//.test(normalized) &&
        !normalized.split('/').some(part => part === '..');
      if (!isDir && safe && Number.isFinite(size) && IMAGE_EXTENSIONS.test(normalized)) {
        entries.push({ path: normalized, size });
      }
    }
    current = {};
  }
  for (const line of lines) {
    if (line.trim() === '') { flush(); continue; }
    const idx = line.indexOf(' = ');
    if (idx !== -1) current[line.slice(0, idx)] = line.slice(idx + 3);
  }
  flush();
  return entries;
}

/** Extracts only recognized disc-image entries to the browser's OPFS. */
export async function extractIsoEntriesToOpfs({ archive, destPath, onProgress }) {
  if (!archive || typeof archive.slice !== 'function' || !Number.isFinite(archive.size)) {
    throw new Error('Choose a .7z archive file.');
  }
  if (typeof destPath !== 'string' || destPath.startsWith('/') ||
      destPath.split('/').some(part => part === '..')) {
    throw new Error('Invalid temporary extraction folder.');
  }
  const lines = [];
  let phase = 'list';
  let currentFile = null;
  let processedBytes = 0;
  let lastProgressAt = 0;
  const sevenZip = await SevenZipFactory({
    print: line => {
      if (phase === 'list') lines.push(line);
      else {
        const match = /-\s(.+)$/.exec(line);
        if (match) currentFile = match[1];
      }
    },
    printErr: () => { },
  });

  sevenZip.FS.mkdir(INPUT_MOUNT);
  sevenZip.FS.mount(makeBlobInputFs(sevenZip.FS, archive), {}, INPUT_MOUNT);
  sevenZip.FS.mkdir(MOUNT);
  sevenZip.FS.mount(sevenZip.OPFS, {}, MOUNT);

  onProgress?.({ phase: 'listing', processedBytes: 0, totalBytes: 0, currentFile: null });
  const listExit = await sevenZip.callMain(['l', '-slt', ARCHIVE_PATH]);
  if (listExit !== 0) throw new Error('7z archive listing failed. The archive may be damaged or password-protected.');
  const imageEntries = parseArchiveEntries(lines);
  if (!imageEntries.length) throw new Error('No ISO/XISO/XSF/IMG/BIN image was found in this .7z archive.');
  const totalBytes = imageEntries.reduce((sum, entry) => sum + entry.size, 0);
  try {
    const storage = typeof navigator !== 'undefined' ? await navigator.storage?.estimate?.() : null;
    if (storage && Number.isFinite(storage.quota) && Number.isFinite(storage.usage) &&
        storage.quota - storage.usage < totalBytes) {
      throw new Error('Not enough browser site storage for the selected image files. Free space or use another browser profile/device, then retry.');
    }
  } catch (err) {
    if (err && err.message && err.message.startsWith('Not enough browser site storage')) throw err;
    // Storage estimates are advisory and unavailable in some browser builds;
    // let OPFS report a real quota error if the estimate cannot be obtained.
  }
  onProgress?.({ phase: 'extracting', processedBytes: 0, totalBytes, currentFile: null });

  sevenZip.OPFS.onWrite = (_path, bytesWritten) => {
    // The write callback can include filesystem bookkeeping; cap the display
    // at the selected image total so progress never exceeds 100 percent.
    processedBytes = Math.min(totalBytes, processedBytes + Math.max(0, Number(bytesWritten) || 0));
    const now = performance.now();
    if (now - lastProgressAt >= 100 || processedBytes >= totalBytes) {
      lastProgressAt = now;
      onProgress?.({ phase: 'extracting', processedBytes, totalBytes, currentFile });
    }
  };

  phase = 'extract';
  const destFsPath = `${MOUNT}/${destPath}`;
  const args = ['x', ARCHIVE_PATH, `-o${destFsPath}`, '-y', '-bb1', '-bso1', '-spd', '--', ...imageEntries.map(entry => entry.path)];
  const extractExit = await sevenZip.callMain(args);
  if (extractExit !== 0) throw new Error('7z extraction failed. Check the archive, password protection, and available browser storage.');
  onProgress?.({ phase: 'done', processedBytes: totalBytes, totalBytes, currentFile: null });
  return { entries: imageEntries, totalBytes };
}

const isDedicatedWorker = typeof WorkerGlobalScope !== 'undefined' && self instanceof WorkerGlobalScope;
if (isDedicatedWorker) {
  self.onmessage = async event => {
    const msg = event.data;
    if (!msg || msg.type !== 'extract') return;
    const { id, archive, destPath } = msg;
    try {
      const result = await extractIsoEntriesToOpfs({
        archive, destPath,
        onProgress: info => self.postMessage({ type: 'progress', id, ...info }),
      });
      self.postMessage({ type: 'done', id, entries: result.entries, totalBytes: result.totalBytes });
    } catch (err) {
      self.postMessage({ type: 'error', id, message: err?.message ?? String(err), stack: err?.stack });
    }
  };
}
