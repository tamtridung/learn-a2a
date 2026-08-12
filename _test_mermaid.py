import base64
import urllib.request
import urllib.error

ORIG = """sequenceDiagram
    participant C as Client (Notebook)
    participant B as Booking Agent
    C->>B: SendMessage("Đặt vé Hà Nội -> Đà Nẵng")
    B-->>C: status: working
    B-->>C: status: INPUT-REQUIRED "Bạn xác nhận đặt vé...? (có/không)"
    Note over C: ⏸️ Hỏi người dùng
    C->>B: SendMessage(CÙNG task_id, "có")
    B-->>C: status: working
    B-->>C: artifact: "ĐẶT VÉ THÀNH CÔNG!"
    B-->>C: status: completed
"""

FIXED = """sequenceDiagram
    participant C as Client (Notebook)
    participant B as Booking Agent
    C->>B: SendMessage("Đặt vé Hà Nội → Đà Nẵng")
    B-->>C: status: working
    B-->>C: status: INPUT-REQUIRED "Bạn xác nhận đặt vé...? (có/không)"
    Note over C: ⏸️ Hỏi người dùng
    C->>B: SendMessage(cùng task_id, "có")
    B-->>C: status: working
    B-->>C: artifact: "ĐẶT VÉ THÀNH CÔNG!"
    B-->>C: status: completed
"""


def test(code, label):
    encoded = base64.urlsafe_b64encode(code.encode("utf-8")).decode().rstrip("=")
    url = f"https://mermaid.ink/img/{encoded}?type=png"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=60) as r:
            data = r.read()
            ct = r.headers.get("Content-Type")
            print(f"[{label}] OK -> {ct}, {len(data)} bytes")
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", "replace")
        print(f"[{label}] ERROR {e.code}: {body[:800]}")
    except Exception as e:
        print(f"[{label}] EXC: {type(e).__name__}: {e}")


test(ORIG, "ORIGINAL")
test(FIXED, "FIXED")
