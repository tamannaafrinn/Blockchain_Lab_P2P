"""Application-level protocol: [4-byte length][JSON payload], then optional raw bytes."""
import json
import os
import struct

CHUNK_SIZE = 64 * 1024            # 64 KB chunks for file transfer
MAX_MSG_SIZE = 1024 * 1024        # sanity limit for a JSON message (1 MB)
_HEADER = struct.Struct("!I")     # 4-byte unsigned int, network byte order


def send_msg(sock, obj):
    """Encode a dict as JSON and send it with a 4-byte length prefix."""
    data = json.dumps(obj).encode("utf-8")
    sock.sendall(_HEADER.pack(len(data)) + data)


def recv_exact(sock, n):
    """Read exactly n bytes (recv() may return fewer, so loop)."""
    buf = bytearray()
    while len(buf) < n:
        chunk = sock.recv(min(CHUNK_SIZE, n - len(buf)))
        if not chunk:
            raise ConnectionError("Peer disconnected")
        buf.extend(chunk)
    return bytes(buf)


def recv_msg(sock):
    """Read one length-prefixed JSON message and return it as a dict."""
    (length,) = _HEADER.unpack(recv_exact(sock, _HEADER.size))
    if length == 0 or length > MAX_MSG_SIZE:
        raise ValueError(f"Invalid message length: {length}")
    return json.loads(recv_exact(sock, length).decode("utf-8"))


def send_file_bytes(sock, path):
    """Send raw file bytes in 64 KB chunks (never loads the whole file)."""
    with open(path, "rb") as f:
        while True:
            chunk = f.read(CHUNK_SIZE)
            if not chunk:
                break
            sock.sendall(chunk)


def recv_file_bytes(sock, dest_path, size):
    """Receive exactly `size` bytes from the socket and write them to dest_path."""
    remaining = size
    with open(dest_path, "wb") as f:
        while remaining > 0:
            chunk = sock.recv(min(CHUNK_SIZE, remaining))
            if not chunk:
                raise ConnectionError("Peer disconnected during file transfer")
            f.write(chunk)
            remaining -= len(chunk)


def unique_path(folder, filename):
    """Return a safe path inside folder that does not overwrite existing files."""
    name = os.path.basename(filename) or "received_file"
    base, ext = os.path.splitext(name)
    path, i = os.path.join(folder, name), 1
    while os.path.exists(path):
        path = os.path.join(folder, f"{base}_{i}{ext}")
        i += 1
    return path
