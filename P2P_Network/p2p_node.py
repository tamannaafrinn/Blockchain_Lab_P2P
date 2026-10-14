"""P2P node: every peer is a TCP server (accepts) AND a TCP client (connects)."""
import ipaddress
import os
import socket
import threading
import uuid

import protocol

DOWNLOAD_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "downloads")


class Peer:
    def __init__(self, peer_id, name, ip, port, sock):
        self.id, self.name, self.ip, self.port, self.sock = peer_id, name, ip, port, sock
        self.send_lock = threading.Lock()   # one sender at a time per connection


class P2PNode:
    def __init__(self, name, port, emit):
        """emit(kind, text): kind is 'system' | 'msg' | 'error' | 'peers'."""
        self.name, self.port, self.emit = name, port, emit
        self.peer_id = uuid.uuid4().hex[:8]
        self.peers = {}                      # peer_id -> Peer
        self.lock = threading.Lock()
        self.running = False
        self.server = None

    # ---------------- server role ----------------
    def start(self):
        self.server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.server.bind(("0.0.0.0", self.port))
        self.server.listen()
        self.running = True
        os.makedirs(DOWNLOAD_DIR, exist_ok=True)
        threading.Thread(target=self._accept_loop, daemon=True).start()
        self.emit("system", f"Peer started: {self.name} [{self.peer_id}] on port {self.port}")

    def _accept_loop(self):
        while self.running:
            try:
                conn, addr = self.server.accept()
            except OSError:
                break
            threading.Thread(target=self._handle_incoming, args=(conn, addr), daemon=True).start()

    def _handle_incoming(self, conn, addr):
        try:
            conn.settimeout(10)
            hello = protocol.recv_msg(conn)
            if hello.get("type") != "hello":
                raise ValueError("Expected hello")
            protocol.send_msg(conn, {"type": "hello_ack", "peer_id": self.peer_id,
                                     "peer_name": self.name, "port": self.port})
            conn.settimeout(None)
            peer = Peer(hello["peer_id"], hello["peer_name"], addr[0], int(hello["port"]), conn)
        except (OSError, ValueError, KeyError) as e:
            self.emit("error", f"Incoming handshake failed: {e}")
            conn.close()
            return
        if self._register(peer):
            self.emit("system", f"{peer.name} connected ({peer.ip}:{peer.port})")
            self._listen(peer)
        else:
            conn.close()

    # ---------------- client role ----------------
    def connect(self, ip, port):
        try:
            ipaddress.ip_address(ip)
        except ValueError:
            self.emit("error", f"Invalid IP address: {ip}")
            return False
        if not (1 <= port <= 65535):
            self.emit("error", f"Invalid port: {port}")
            return False
        try:
            sock = socket.create_connection((ip, port), timeout=5)
            protocol.send_msg(sock, {"type": "hello", "peer_id": self.peer_id,
                                     "peer_name": self.name, "port": self.port})
            ack = protocol.recv_msg(sock)
            if ack.get("type") != "hello_ack":
                raise ValueError("Expected hello_ack")
            sock.settimeout(None)
            peer = Peer(ack["peer_id"], ack["peer_name"], ip, int(ack["port"]), sock)
        except (OSError, ValueError, KeyError) as e:
            self.emit("error", f"Connection failed: {e}")
            return False
        if not self._register(peer):
            sock.close()
            return False
        self.emit("system", f"Connected to {peer.name} ({ip}:{port})")
        threading.Thread(target=self._listen, args=(peer,), daemon=True).start()
        return True

    # ---------------- peer table ----------------
    def _register(self, peer):
        if peer.id == self.peer_id:
            self.emit("error", "Cannot connect to yourself")
            return False
        with self.lock:
            if peer.id in self.peers:
                self.emit("error", f"Already connected to {peer.name}")
                return False
            self.peers[peer.id] = peer
        self.emit("peers", "")
        return True

    def _remove(self, peer):
        with self.lock:
            removed = self.peers.pop(peer.id, None)
        try:
            peer.sock.close()
        except OSError:
            pass
        if removed and self.running:
            self.emit("system", f"{peer.name} disconnected")
            self.emit("peers", "")

    def get_peers(self):
        with self.lock:
            return list(self.peers.values())

    # ---------------- receiving ----------------
    def _listen(self, peer):
        try:
            while True:
                msg = protocol.recv_msg(peer.sock)
                kind = msg.get("type")
                if kind == "text":
                    self.emit("msg", f"{peer.name} -> You: {msg['message']}")
                elif kind == "file":
                    size = int(msg["filesize"])
                    if size < 0:
                        raise ValueError("Invalid file size")
                    path = protocol.unique_path(DOWNLOAD_DIR, msg["filename"])
                    self.emit("system", f"Receiving {os.path.basename(path)} ({size} bytes) from {peer.name}...")
                    protocol.recv_file_bytes(peer.sock, path, size)
                    self.emit("msg", f"{peer.name} -> You: File received: {os.path.basename(path)}")
                elif kind == "bye":
                    break
        except (OSError, ValueError, KeyError) as e:
            if self.running:
                self.emit("error", f"Connection with {peer.name} lost: {e}")
        finally:
            self._remove(peer)

    # ---------------- sending ----------------
    def _get(self, peer_id):
        with self.lock:
            peer = self.peers.get(peer_id)
        if not peer:
            self.emit("error", "Selected peer is no longer connected")
        return peer

    def send_text(self, peer_id, text):
        peer = self._get(peer_id)
        if not peer:
            return
        try:
            with peer.send_lock:
                protocol.send_msg(peer.sock, {"type": "text", "sender_id": self.peer_id,
                                              "sender_name": self.name, "message": text})
            self.emit("msg", f"You -> {peer.name}: {text}")
        except OSError as e:
            self.emit("error", f"Send failed: {e}")
            self._remove(peer)

    def send_file(self, peer_id, path):
        peer = self._get(peer_id)
        if not peer:
            return
        if not os.path.isfile(path):
            self.emit("error", f"File does not exist: {path}")
            return
        size = os.path.getsize(path)
        name = os.path.basename(path)
        try:
            with peer.send_lock:
                protocol.send_msg(peer.sock, {"type": "file", "sender_id": self.peer_id,
                                              "sender_name": self.name,
                                              "filename": name, "filesize": size})
                protocol.send_file_bytes(peer.sock, path)
            self.emit("msg", f"You -> {peer.name}: File sent: {name} ({size} bytes)")
        except OSError as e:
            self.emit("error", f"File transfer failed: {e}")
            self._remove(peer)   # stream is out of sync, so drop the connection

    # ---------------- shutdown ----------------
    def stop(self):
        self.running = False
        for peer in self.get_peers():
            try:
                with peer.send_lock:
                    protocol.send_msg(peer.sock, {"type": "bye"})
            except OSError:
                pass
            try:
                peer.sock.close()
            except OSError:
                pass
        with self.lock:
            self.peers.clear()
        if self.server:
            self.server.close()
        self.emit("peers", "")
