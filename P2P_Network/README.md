# UAP P2P Network: Communication and File Sharing

Course: CSE 433 – Blockchain & Distributed Security Lab
Department of CSE, University of Asia Pacific
Student: Sadia Afrin Tamanna
ID: 22201137
Section: C2

## 1. Project Description

A lightweight peer-to-peer (P2P) application written in Python using TCP sockets.
There is **no central server**. Every running instance (peer) is both:

- a **TCP server**, which accepts incoming connections from other peers, and
- a **TCP client**, which connects to other peers using an IP address and port.

Peers can exchange **text messages** and **files** (text, images, audio, video, PDF, ZIP, or any
other binary file) directly. A Tkinter GUI is provided, and several peers can be connected at once.

### Features
- Start a peer with a name and a listening port
- Connect to other peers by IP and port
- HELLO / HELLO_ACK handshake exchanging peer ID, name and port
- Connected peer list
- Text messaging to a selected peer
- Binary file transfer in 64 KB chunks (no whole-file loading into memory)
- One thread per connection, so multiple peers work concurrently
- Error handling for invalid IP or port, refused connections, missing files, sudden disconnects, and sending with no peer selected

### Protocol
Every message is framed as `[4-byte length][JSON payload]`:

| Type        | Purpose                                                      |
|-------------|--------------------------------------------------------------|
| `hello`     | Sent by the connecting peer to introduce itself              |
| `hello_ack` | Reply from the accepting peer                                |
| `text`      | Text message (`sender_id`, `sender_name`, `message`)         |
| `file`      | File metadata (`filename`, `filesize`), followed by raw bytes |
| `bye`       | Graceful disconnect                                          |

For files, the receiver reads **exactly `filesize` bytes** after the metadata and saves them to
`downloads/`. Existing files are never overwritten (`photo.jpg` becomes `photo_1.jpg`).

## 2. Requirements

- Python **3.9 or later**
- Windows, Linux or macOS
- Tkinter (bundled with Python on Windows and macOS; on Ubuntu/Debian run `sudo apt install python3-tk`)
- No third-party packages (standard library only: `socket`, `threading`, `json`, `struct`, `tkinter`)
- For LAN testing: all computers on the same Wi-Fi/LAN

## 3. Installation / Setup

1. Install Python 3.9+ from https://www.python.org (on Windows tick **Add Python to PATH**).
2. Unzip the project and open the `P2P_Network` folder (in VS Code: File, then Open Folder).
3. Check the layout:

```
P2P_Network/
|-- main.py          # GUI
|-- p2p_node.py      # networking: server + client, threads, text and file transfer
|-- protocol.py      # message framing and file byte helpers
|-- requirements.txt
|-- README.md
|-- screenshots/
`-- downloads/       # received files are saved here
```

4. No `pip install` is needed.

## 4. How to Run

Open a terminal in the project folder and run:

```
python main.py
```

(use `python3 main.py` on Linux/macOS). Run the command again in another terminal for each
extra peer.

## 5. How to Connect Two Peers

**Same computer**

1. **Peer A:** Name `Alice`, Port `5000`, click **Start Peer**.
2. **Peer B** (second terminal): Name `Bob`, Port `5001`, click **Start Peer**.
3. In Bob's window under *Connect to Another Peer* enter IP `127.0.0.1`, Port `5000`, click **Connect**.
4. Both windows now list each other under **Connected Peers**.

Each peer on the same computer needs a **different port**, because only one socket can listen on a port.

**Two computers on the same LAN**

1. On Computer A, start a peer; its LAN IP is shown in the window (e.g. `192.168.1.10`).
2. On Computer B, start a peer, then connect to `192.168.1.10` and port `5000`.
3. If the connection fails, allow Python through the firewall (private network).

**Three or more peers:** start Charlie (port `5002`) and connect it to Alice and to Bob.
Every peer you connect to appears in the list, and you choose which one to talk to.

## 6. How to Send Messages and Transfer Files

**Text:** select a peer in the *Connected Peers* list, type in the *Send Text* box, and press
**Enter** or click **Send**.

**Files:**
1. Select a peer in the *Connected Peers* list.
2. Click **Choose File & Send** and pick any file (image, audio, video, PDF, ZIP, ...).
3. The sender's log shows `File sent: name (N bytes)`.
4. The receiver's log shows `File received: name`, and the file is stored in `downloads/`.

If no peer is selected, the app shows `[ERROR] Select a peer from the list first`.

## 7. Example Screenshots

> Replace these with your own screenshots saved in the `screenshots/` folder.

| Screenshot | File |
|---|---|
| Peer 1 (Alice) connected and receiving | `screenshots/peer connect.png` |
| Peer 2 (Bob) sending a file | `screenshots/peer Text.png` |
| Peer 3 (Charlie) joining the network | `screenshots/peer file share.png` |

![Peer 1](screenshots/peer connect.png)
![Peer 2](screenshots/peer Text.png)
![Peer 3](screenshots/peer file share.png)

