"""Tkinter GUI for the Tamanna Home Network. Run with: python main.py"""
import queue
import socket
import threading
import tkinter as tk
from tkinter import filedialog, messagebox, scrolledtext, ttk

from p2p_node import P2PNode


def local_ip():
    """Best-effort LAN IP (no packets are actually sent)."""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except OSError:
        return "127.0.0.1"


class App:
    def __init__(self, root):
        self.root = root
        root.title("Tamanna Home Network")
        root.geometry("900x600")
        self.node = None
        self.events = queue.Queue()      # worker threads -> GUI thread
        self.peer_ids = []
        self._build()
        self._set_running(False)
        root.protocol("WM_DELETE_WINDOW", self._on_close)
        self._poll()

    # ---------- UI ----------
    def _build(self):
        f = ttk.LabelFrame(self.root, text="My Peer")
        f.pack(fill="x", padx=8, pady=4)
        self.name_var, self.port_var = tk.StringVar(value="Alice"), tk.StringVar(value="5000")
        ttk.Label(f, text="Name:").pack(side="left", padx=4)
        self.name_entry = ttk.Entry(f, textvariable=self.name_var, width=16)
        self.name_entry.pack(side="left")
        ttk.Label(f, text="Port:").pack(side="left", padx=4)
        self.port_entry = ttk.Entry(f, textvariable=self.port_var, width=8)
        self.port_entry.pack(side="left")
        self.start_btn = ttk.Button(f, text="Start Peer", command=self._start)
        self.start_btn.pack(side="left", padx=6)
        self.stop_btn = ttk.Button(f, text="Stop", command=self._stop)
        self.stop_btn.pack(side="left")
        self.info = ttk.Label(f, text=f"My LAN IP: {local_ip()}")
        self.info.pack(side="left", padx=12)

        c = ttk.LabelFrame(self.root, text="Connect to Another Peer")
        c.pack(fill="x", padx=8, pady=4)
        self.ip_var, self.rport_var = tk.StringVar(value="127.0.0.1"), tk.StringVar(value="5000")
        ttk.Label(c, text="IP:").pack(side="left", padx=4)
        ttk.Entry(c, textvariable=self.ip_var, width=18).pack(side="left")
        ttk.Label(c, text="Port:").pack(side="left", padx=4)
        ttk.Entry(c, textvariable=self.rport_var, width=8).pack(side="left")
        self.conn_btn = ttk.Button(c, text="Connect", command=self._connect)
        self.conn_btn.pack(side="left", padx=6)

        mid = ttk.Frame(self.root)
        mid.pack(fill="both", expand=True, padx=8, pady=4)
        left = ttk.LabelFrame(mid, text="Connected Peers")
        left.pack(side="left", fill="y")
        self.listbox = tk.Listbox(left, width=32, exportselection=False)
        self.listbox.pack(fill="both", expand=True, padx=4, pady=4)
        right = ttk.LabelFrame(mid, text="Messages / Events")
        right.pack(side="left", fill="both", expand=True, padx=(8, 0))
        self.log = scrolledtext.ScrolledText(right, state="disabled", wrap="word")
        self.log.pack(fill="both", expand=True, padx=4, pady=4)
        self.log.tag_config("error", foreground="red")
        self.log.tag_config("system", foreground="gray30")

        t = ttk.LabelFrame(self.root, text="Send Text")
        t.pack(fill="x", padx=8, pady=4)
        self.text_var = tk.StringVar()
        entry = ttk.Entry(t, textvariable=self.text_var)
        entry.pack(side="left", fill="x", expand=True, padx=4, pady=4)
        entry.bind("<Return>", lambda e: self._send_text())
        self.send_btn = ttk.Button(t, text="Send", command=self._send_text)
        self.send_btn.pack(side="right", padx=4)

        fl = ttk.LabelFrame(self.root, text="Send File")
        fl.pack(fill="x", padx=8, pady=4)
        ttk.Label(fl, text="Text, image, audio, video, PDF, ZIP, etc.").pack(side="left", padx=4)
        self.file_btn = ttk.Button(fl, text="Choose File & Send", command=self._send_file)
        self.file_btn.pack(side="right", padx=4, pady=4)

        self.status = tk.StringVar(value="Not running")
        ttk.Label(self.root, textvariable=self.status, relief="sunken", anchor="w").pack(fill="x", side="bottom")

    def _set_running(self, running):
        for w in (self.name_entry, self.port_entry, self.start_btn):
            w.config(state="disabled" if running else "normal")
        for w in (self.stop_btn, self.conn_btn, self.send_btn, self.file_btn):
            w.config(state="normal" if running else "disabled")

    def _log(self, kind, text):
        self.log.config(state="normal")
        self.log.insert("end", (f"[{kind.upper()}] " if kind in ("system", "error") else "") + text + "\n", kind)
        self.log.see("end")
        self.log.config(state="disabled")

    def _poll(self):
        while not self.events.empty():
            kind, text = self.events.get()
            if kind == "peers":
                self._refresh_peers()
            else:
                self._log(kind, text)
                self.status.set(text)
        self.root.after(100, self._poll)

    def _refresh_peers(self):
        selected = self._selected_id()
        self.listbox.delete(0, "end")
        self.peer_ids = []
        if self.node:
            for p in self.node.get_peers():
                self.listbox.insert("end", f"{p.name} [{p.id}]  {p.ip}:{p.port}")
                self.peer_ids.append(p.id)
        if selected in self.peer_ids:
            self.listbox.selection_set(self.peer_ids.index(selected))

    def _selected_id(self):
        sel = self.listbox.curselection()
        return self.peer_ids[sel[0]] if sel and sel[0] < len(self.peer_ids) else None

    # ---------- actions ----------
    def _emit(self, kind, text):
        self.events.put((kind, text))

    def _start(self):
        name = self.name_var.get().strip()
        if not name:
            return messagebox.showerror("Error", "Enter a peer name")
        try:
            port = int(self.port_var.get())
            if not 1 <= port <= 65535:
                raise ValueError
        except ValueError:
            return messagebox.showerror("Error", "Port must be a number between 1 and 65535")
        node = P2PNode(name, port, self._emit)
        try:
            node.start()
        except OSError as e:
            return messagebox.showerror("Error", f"Cannot start peer: {e}")
        self.node = node
        self._set_running(True)
        self.info.config(text=f"{name} [{node.peer_id}] | {local_ip()}:{port}")

    def _stop(self):
        if self.node:
            self.node.stop()
            self.node = None
        self._set_running(False)
        self._refresh_peers()
        self.info.config(text=f"My LAN IP: {local_ip()}")
        self._log("system", "Peer stopped")

    def _connect(self):
        ip = self.ip_var.get().strip()
        try:
            port = int(self.rport_var.get())
        except ValueError:
            return self._log("error", "Invalid port")
        threading.Thread(target=self.node.connect, args=(ip, port), daemon=True).start()

    def _send_text(self):
        pid, text = self._selected_id(), self.text_var.get().strip()
        if not pid:
            return self._log("error", "Select a peer from the list first")
        if not text:
            return
        self.text_var.set("")
        threading.Thread(target=self.node.send_text, args=(pid, text), daemon=True).start()

    def _send_file(self):
        pid = self._selected_id()
        if not pid:
            return self._log("error", "Select a peer from the list first")
        path = filedialog.askopenfilename(title="Choose a file to send")
        if path:
            self._log("system", f"Sending {path} ...")
            threading.Thread(target=self.node.send_file, args=(pid, path), daemon=True).start()

    def _on_close(self):
        if self.node:
            self.node.stop()
        self.root.destroy()


if __name__ == "__main__":
    root = tk.Tk()
    App(root)
    root.mainloop()
