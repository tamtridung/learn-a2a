# -*- coding: utf-8 -*-
"""Script sinh ra notebook A2A_MultiAgent_Notebook.ipynb (tránh lỗi escape JSON khi viết tay)."""
import json

CELLS = []


def md(text):
    CELLS.append({"cell_type": "markdown", "metadata": {}, "source": text.splitlines(keepends=True)})


def code(text):
    CELLS.append({"cell_type": "code", "execution_count": None, "metadata": {}, "outputs": [], "source": text.splitlines(keepends=True)})


# =====================================================================
# MỞ ĐẦU
# =====================================================================
md("""# 🏗️ Xây dựng hệ thống A2A Multi-Agent với DeepAgents

Chào bạn! Notebook này là một **khóa học thực hành** dạy bạn từng bước xây dựng một hệ thống **A2A multi-agent**:
một **orchestrator** (điều phối viên) chỉ huy **3 agent chuyên môn** bên dưới — mỗi agent được xây bằng framework **DeepAgents**.

## 🎯 Mục tiêu

Sau khóa học này bạn sẽ:

1. Hiểu **A2A (Agent2Agent) là gì** và vì sao các agent cần nói chuyện với nhau theo một "ngôn ngữ chung".
2. Biết các **khối xây dựng cốt lõi** của A2A: `AgentCard`, `Task`, `Message`, `Part`, `Artifact`.
3. Biết cách **đóng gói một DeepAgent thành một A2A Server** (để agent khác gọi được qua mạng).
4. Biết cách dùng **A2A Client** để gọi một agent từ xa.
5. Xây được một **orchestrator** dùng DeepAgents để tự quyết định gọi agent nào.

## 🧠 Giả định về bạn

- Bạn **chưa biết gì về A2A** — tôi sẽ giải thích từ con số 0, kèm ví dụ dễ hiểu như học sinh cấp 3.
- Bạn **đã biết DeepAgents** (`create_deep_agent`, tools, invoke...) — phần này tôi chỉ ôn lại ngắn gọn.

## 🏛️ Kiến trúc hệ thống chúng ta sẽ xây

```mermaid
graph TD
    U([👤 Người dùng]) -->|A2A - gửi câu hỏi| O[🧑‍💼 Orchestrator<br/>DeepAgent + A2A Client]
    O -->|A2A protocol| W[🌤️ Weather Agent<br/>DeepAgent]
    O -->|A2A protocol| N[📰 News Agent<br/>DeepAgent]
    O -->|A2A protocol| C[💱 Currency Agent<br/>DeepAgent]
```

| Thành phần | Nhiệm vụ | Cổng (port) |
|---|---|---|
| `weather_agent.py` | Trả lời thời tiết theo thành phố | 41251 |
| `news_agent.py` | Trả lời tin tức theo chủ đề | 41252 |
| `currency_agent.py` | Chuyển đổi tiền tệ | 41253 |
| `orchestrator_agent.py` | Nghe người dùng, gọi 3 agent trên, tổng hợp kết quả | 41241 |

> 💡 **Mẹo học:** Mỗi agent chạy như **một dịch vụ riêng biệt** (tiến trình riêng, cổng riêng). Đây giống như các công ty khác nhau trên Internet — họ không biết code nội bộ của nhau, chỉ nói chuyện qua **giao thức chuẩn** A2A.
""")

# =====================================================================
# CHƯƠNG 1 - A2A LÀ GÌ
# =====================================================================
md("""# Chương 1 — A2A là gì? (Giải thích cho người mới)

## 1.1 Vấn đề: các agent "sống cô lập"

Hãy tưởng tượng bạn có 3 "trợ lý tài năng" nhưng mỗi người chỉ nói **một thứ tiếng riêng**:

- Anh **Weather** — giỏi thời tiết, chỉ nói tiếng Anh.
- Chị **News** — giỏi tin tức, chỉ nói tiếng Pháp.
- Anh **Currency** — giỏi tiền tệ, chỉ nói tiếng Nhật.

Muốn họ phối hợp, bạn không thể "nhét" họ vào một cái máy duy nhất (mỗi người có bí quyết riêng, chạy ở công ty riêng). Bạn cần một **ngôn ngữ chung** để họ trao đổi. Đó chính là **A2A Protocol** 🎉

**A2A = Agent2Agent**: một **tiêu chuẩn mở** (open standard) định nghĩa *cách các AI agent nói chuyện với nhau*, bất kể chúng được viết bằng framework nào (LangChain, DeepAgents, ADK, ...) hay thuộc công ty nào.

## 1.2 Ba "diễn viên" chính

```mermaid
graph LR
    U([👤 User]) --> C([🤖 A2A Client])
    C -->|"A2A qua HTTP/JSON-RPC"| S([🤖 A2A Server - Remote Agent])
```

| Diễn viên | Vai trò | Ví dụ trong khóa học |
|---|---|---|
| **User** | Người dùng cuối đưa ra yêu cầu | Bạn, người gõ câu hỏi |
| **A2A Client** | Bên chủ động gửi yêu cầu | Hàm `call_agent()` chúng ta viết; hoặc chính **orchestrator** |
| **A2A Server** | Bên nhận yêu cầu, làm việc, trả kết quả | 3 worker agents + orchestrator |

> 📌 **Điểm mấu chốt:** Một agent thường **vừa là Server** (nhận yêu cầu từ bên trên) **vừa là Client** (gửi yêu cầu xuống bên dưới). Orchestrator của chúng ta chính là "vừa ông chủ, vừa người đi làm".

## 1.3 Các "viên gạch" dữ liệu của A2A

| Khái niệm | Là gì (nói nôm na) | Tên trong code |
|---|---|---|
| **Agent Card** | "Danh thiếp số": agent là ai, giỏi gì, nói chuyện qua đâu | `AgentCard` |
| **Task** | "Phiếu công việc" có số hiệu, có vòng đời (đang làm → xong) | `Task`, `TaskState` |
| **Message** | Một lượt nói chuyện (ai nói, nói gì) | `Message` |
| **Part** | "Phong bì" chứa nội dung (text, file, dữ liệu JSON) | `Part` |
| **Artifact** | "Bàn giao sản phẩm": kết quả cụ thể của Task | `Artifact` |

**Ví dụ analogy — đặt món ở nhà hàng 🍜:**
- **Agent Card** = menu + tên quán: "Quán ABC chuyên món Việt, nhận đặt qua app".
- **Message** = "Cho tôi một tô phở".
- **Task** = phiếu đặt món số #0012 (có thể theo dõi: *đã nhận → đang nấu → hoàn thành*).
- **Part** = nội dung trong phiếu: tô phở, ít hành, thêm ớt.
- **Artifact** = tô phở được bưng ra bàn. 🍜

## 1.4 Vòng đời của một Task

```mermaid
sequenceDiagram
    participant C as Client
    participant S as A2A Server
    C->>S: SendMessage("Thời tiết Hà Nội?")
    S-->>C: Task (submitted) - "đã nhận phiếu"
    S-->>C: status: working - "đang xử lý"
    S-->>C: artifact: "Hà Nội: 28°C, nắng nhẹ"
    S-->>C: status: completed - "hoàn thành"
```

Các trạng thái quan trọng: `submitted` (đã nhận) → `working` (đang làm) → `completed` (xong). Ngoài ra còn có `failed` (lỗi), `canceled` (huỷ), `input-required` (cần hỏi thêm).

## 1.5 Vận chuyển: nói chuyện bằng gì?

A2A chạy trên **HTTP** và nội dung đóng gói theo **JSON-RPC 2.0**. SDK Python hỗ trợ sẵn nhiều "phương tiện vận chuyển":

- **JSON-RPC** (chuẩn, ta dùng cái này)
- **HTTP+JSON (REST)**
- **gRPC** (hiệu năng cao)

Ta không cần tự code JSON-RPC — SDK `a2a-sdk` lo hết. Ta chỉ viết "bộ não" và "danh thiếp".

---

### ✅ Kiểm tra nhanh cài đặt

Chạy cell dưới để chắc chắn `a2a-sdk` đã được cài trong môi trường.
""")

code("""from importlib.metadata import version

for pkg in ["a2a-sdk", "deepagents", "uvicorn"]:
    try:
        print(f"{pkg}: {version(pkg)}")
    except Exception as exc:
        print(f"{pkg}: CHƯA CÀI ({exc})")""")

# =====================================================================
# CHƯƠNG 2 - CHUẨN BỊ DỰ ÁN
# =====================================================================
md("""# Chương 2 — Chuẩn bị "không gian làm việc"

Ta sẽ đặt toàn bộ code của hệ thống vào thư mục `my_a2a_system/` (nằm cạnh notebook).
Mỗi agent là một file `.py` độc lập — giống như mỗi "công ty" có văn phòng riêng.
""")

code("""import os
import sys

# Thư mục chứa toàn bộ "mã nguồn" của hệ thống A2A
PROJECT_DIR = os.path.join(os.getcwd(), "my_a2a_system")
os.makedirs(PROJECT_DIR, exist_ok=True)

# Để notebook có thể import các hàm tiện ích chung (a2a_common)
if PROJECT_DIR not in sys.path:
    sys.path.insert(0, PROJECT_DIR)

print("Thư mục dự án:", PROJECT_DIR)""")

# =====================================================================
# CHƯƠNG 3 - CHẾ ĐỘ MOCK
# =====================================================================
md("""# Chương 3 — Chế độ MOCK (học không tốn tiền) ⚙️

**Vấn đề:** Gọi DeepAgent thật cần API key (tốn phí, cần mạng). Nhưng mục tiêu chính của khóa học này là **hiểu A2A** — phần "ống nước" giao tiếp — chứ không phải trí thông minh của agent.

**Giải pháp:** Mỗi agent sẽ có **2 bộ não**:

| Bộ não | Khi nào dùng | Mục đích |
|---|---|---|
| 🧠 **DeepAgent** (thật) | Có API key | Học cách đóng gói DeepAgent vào A2A |
| 🪄 **Mock brain** (giả) | Không có API key | Học phần giao tiếp A2A, chạy nhanh, miễn phí |

> ⚡ **Điểm quan trọng:** Dù dùng bộ não nào, **phần A2A hoàn toàn giống nhau** — client vẫn gọi server qua HTTP, task vẫn có vòng đời. Chỉ khác "nội dung câu trả lời".

### Bật chế độ DeepAgent thật như thế nào?

Set biến môi trường có API key của provider bạn dùng, ví dụ trên Windows PowerShell:

```powershell
$env:ANTHROPIC_API_KEY = "sk-ant-..."
$env:A2A_DEEPAGENT_MODEL = "anthropic:claude-sonnet-5"
```

| Provider | Biến API key | Ví dụ model |
|---|---|---|
| Anthropic | `ANTHROPIC_API_KEY` | `anthropic:claude-sonnet-5` |
| OpenAI | `OPENAI_API_KEY` | `openai:gpt-5.5` |
| Google | `GOOGLE_API_KEY` | `google_genai:gemini-3.5-flash` |

Chương trình sẽ tự dò: **có API key → dùng DeepAgent; không có → tự chuyển sang MOCK**.

### 📦 Viết file tiện ích chung: `a2a_common.py`

Đây là "hộp dụng cụ" dùng chung cho cả 4 agent. Nó chứa 4 việc:

1. `get_model()` — quyết định dùng DeepAgent thật hay mock.
2. `run_deep_agent()` — chạy một DeepAgent, lấy câu trả lời dạng text.
3. `call_agent()` — **chính là A2A Client**: gọi một server từ xa, gom kết quả.
4. `wait_for_server()` — chờ server sẵn sàng (đọc được Agent Card).

Hãy đọc kỹ comment trong code — mỗi dòng đều có giải thích.
""")

code("""%%writefile {PROJECT_DIR}/a2a_common.py
\"\"\"Các hàm tiện ích dùng chung cho hệ thống A2A mini trong bài học.\"\"\"
import asyncio
import os
import time
import uuid

import httpx

from a2a.client import ClientConfig, create_client
from a2a.helpers import get_artifact_text, get_message_text
from a2a.types import Message, Part, Role, SendMessageRequest, TaskState

# Có .env chứa API key không? Có thì nạp vào.
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

# Model DeepAgents sẽ dùng, định dạng "provider:model".
# Đổi được qua biến môi trường A2A_DEEPAGENT_MODEL.
DEFAULT_MODEL = os.environ.get("A2A_DEEPAGENT_MODEL", "anthropic:claude-sonnet-5")

# Ánh xạ provider -> (các) biến môi trường chứa API key
PROVIDER_KEYS = {
    "anthropic": ("ANTHROPIC_API_KEY",),
    "openai": ("OPENAI_API_KEY",),
    "google_genai": ("GOOGLE_API_KEY", "GEMINI_API_KEY"),
}


def get_model():
    \"\"\"Trả về chuỗi model nếu có đủ API key, ngược lại None (chế độ MOCK).\"\"\"
    provider = DEFAULT_MODEL.split(":")[0]
    key_names = PROVIDER_KEYS.get(provider, ())
    if any(os.environ.get(k) for k in key_names):
        return DEFAULT_MODEL
    return None


async def run_deep_agent(agent, query, thread_id="thread-1"):
    \"\"\"Chạy một DeepAgent với câu hỏi, trả về câu trả lời dạng text.\"\"\"
    result = await agent.ainvoke(
        {"messages": [{"role": "user", "content": query}]},
        config={"configurable": {"thread_id": thread_id}},
    )
    last = result["messages"][-1]
    content = last.content
    # Nội dung có thể là chuỗi đơn giản, hoặc danh sách các "block" (text, image...)
    if isinstance(content, list):
        texts = []
        for block in content:
            if isinstance(block, dict) and block.get("type") == "text":
                texts.append(block.get("text", ""))
        return "\\n".join(t for t in texts if t)
    return str(content)


async def call_agent(base_url, user_text, verbose=True):
    \"\"\"Gọi một A2A server và trả về toàn bộ nội dung trong artifact.

    Đây chính là "khách hàng" (A2A Client):
      1. Resolve Agent Card từ URL (đọc "danh thiếp")
      2. Tạo client
      3. Gửi SendMessage
      4. Lắng nghe dòng sự kiện: status update + artifact update
    \"\"\"
    artifacts = []
    async with httpx.AsyncClient() as httpx_client:
        config = ClientConfig(httpx_client=httpx_client)
        client = await create_client(base_url, client_config=config)

        message = Message(
            role=Role.ROLE_USER,
            message_id=str(uuid.uuid4()),
            parts=[Part(text=user_text)],
        )
        request = SendMessageRequest(message=message)

        # Duyệt qua từng sự kiện server gửi về (stream)
        async for event in client.send_message(request):
            if event.HasField("status_update"):
                state = TaskState.Name(event.status_update.status.state)
                extra = ""
                if event.status_update.status.HasField("message"):
                    extra = get_message_text(
                        event.status_update.status.message, delimiter=" "
                    )
                if verbose:
                    print(f"      [status] {state} {extra}".rstrip())
            elif event.HasField("artifact_update"):
                text = get_artifact_text(
                    event.artifact_update.artifact, delimiter="\\n"
                )
                if text.strip():
                    artifacts.append(text)

        await client.close()
    return "\\n".join(artifacts)


async def wait_for_server(base_url, timeout=90):
    \"\"\"Chờ cho tới khi server phục vụ được Agent Card (tức server đã sẵn sàng).\"\"\"
    card_url = base_url.rstrip("/") + "/.well-known/agent-card.json"
    deadline = time.time() + timeout
    async with httpx.AsyncClient() as client:
        while time.time() < deadline:
            try:
                r = await client.get(card_url, timeout=2.0)
                if r.status_code == 200:
                    return True
            except Exception:
                pass
            await asyncio.sleep(0.5)
    return False""")

# =====================================================================
# CHƯƠNG 4 - BỘ KHUNG A2A SERVER
# =====================================================================
md("""# Chương 4 — Bộ khung của một A2A Server 🏗️

Trước khi viết cả 4 agent, ta hiểu **cấu trúc chung** của một A2A Server trong SDK Python.

Mỗi A2A Server gồm **4 mảnh ghép**:

```mermaid
graph LR
    subgraph "Một A2A Server (file .py)"
        A[Agent Card<br/>danh thiếp] --> D[DefaultRequestHandler<br/>lễ tân]
        D --> E[AgentExecutor<br/>bộ não xử lý]
        E --> T[TaskUpdater<br/>phát thanh viên]
    end
```

| Mảnh ghép | Ví von | Vai trò |
|---|---|---|
| `AgentCard` | 🪪 Danh thiếp | Khai báo agent là ai, giỏi gì, nói chuyện qua đâu |
| `DefaultRequestHandler` | 💁 Lễ tân | Nhận yêu cầu từ mạng, quản lý Task, đưa cho bộ não xử lý |
| `AgentExecutor` | 🧠 Bộ não | **Nơi ta viết code**: đọc câu hỏi, suy nghĩ, trả lời |
| `TaskUpdater` | 📢 Phát thanh viên | Báo cho client biết: đang làm, kết quả, hoàn thành |

### 🧠 `AgentExecutor` — nơi ta viết logic

Ta chỉ cần kế thừa lớp `AgentExecutor` và viết 2 hàm:

- `execute(context, event_queue)` — gọi khi có yêu cầu mới. Đọc `context.get_user_input()` để lấy câu hỏi, rồi dùng `TaskUpdater` để báo tiến trình và trả kết quả.
- `cancel(context, event_queue)` — gọi khi client muốn huỷ task.

### 🔄 Luồng xử lý bên trong `execute()`

```mermaid
sequenceDiagram
    participant F as Framework
    participant E as AgentExecutor (của bạn)
    participant U as TaskUpdater
    F->>E: execute(context, event_queue)
    E->>E: đọc câu hỏi: context.get_user_input()
    E->>U: start_work(...)  → báo "đang làm"
    E->>E: suy nghĩ (gọi DeepAgent / mock brain)
    E->>U: add_artifact(...) → giao kết quả
    E->>U: complete() → báo "xong"
""")

# =====================================================================
# VIẾT 3 WORKER AGENTS
# =====================================================================
md("""# Chương 5 — Viết 3 Worker Agents (DeepAgent + A2A Server) 🌤️📰💱

Mỗi worker là một file `.py` hoàn chỉnh, gồm:

1. **`build_deep_agent()`** — tạo DeepAgent (có tool riêng). Trả về `None` nếu chế độ mock.
2. **`class XxxExecutor(AgentExecutor)`** — bộ não xử lý; bên trong gọi DeepAgent hoặc mock brain.
3. **`create_app()`** — lắp Agent Card + Request Handler + routes thành FastAPI app.
4. **`main()`** — chạy server bằng `uvicorn`.

> 🔍 **Hãy so sánh 3 file:** chúng giống hệt nhau về *khung A2A*; chỉ khác ở *tool* và *mock brain*. Đó chính là triết lý A2A: **"khung giao tiếp chung, trí tuệ riêng"**.
""")

md("""## 5.1 Agent 1 — Weather Agent (`weather_agent.py`) 🌤️

Chạy ở cổng **41251**. Có tool `get_weather(city)`.

```mermaid
graph LR
    U([👤 Người dùng]) --> W[Weather Agent<br/>port 41251]
    W --> T[🛠️ tool: get_weather]
    W --> M[Mock brain]
```
""")

code("""%%writefile {PROJECT_DIR}/weather_agent.py
\"\"\"Weather Agent - một A2A Server với "bộ não" là DeepAgent (hoặc mock).\"\"\"
import argparse
import logging

import uvicorn
from fastapi import FastAPI

from a2a.server.agent_execution.agent_executor import AgentExecutor
from a2a.server.agent_execution.context import RequestContext
from a2a.server.events.event_queue import EventQueue
from a2a.server.request_handlers import DefaultRequestHandler
from a2a.server.routes import (
    add_a2a_routes_to_fastapi,
    create_agent_card_routes,
    create_jsonrpc_routes,
    create_rest_routes,
)
from a2a.server.tasks.inmemory_task_store import InMemoryTaskStore
from a2a.server.tasks.task_updater import TaskUpdater
from a2a.types import (
    AgentCapabilities,
    AgentCard,
    AgentInterface,
    AgentProvider,
    AgentSkill,
    Part,
)

from a2a_common import get_model, run_deep_agent

logger = logging.getLogger(__name__)


def build_deep_agent():
    \"\"\"Tạo DeepAgent làm "bộ não" thật. Chưa có API key -> None (dùng mock).\"\"\"
    model = get_model()
    if model is None:
        return None

    from deepagents import create_deep_agent
    from langchain.tools import tool

    @tool
    def get_weather(city: str) -> str:
        \"\"\"Trả về thời tiết hiện tại của một thành phố.\"\"\"
        table = {
            "hanoi": "Hà Nội: 28°C, trời nắng nhẹ, độ ẩm 75%",
            "hcmc": "TP.HCM: 33°C, nắng nóng, độ ẩm 80%",
            "danang": "Đà Nẵng: 30°C, có mây, khả năng mưa nhẹ",
            "hue": "Huế: 29°C, nắng gián đoạn",
        }
        key = city.strip().lower()
        for k, v in table.items():
            if k in key:
                return v
        return f"{city}: 27°C, trời trong xanh."

    return create_deep_agent(
        name="weather_agent",
        model=model,
        tools=[get_weather],
        system_prompt=(
            "Bạn là chuyên gia thời tiết. Khi được hỏi về thời tiết của một thành phố, "
            "hãy gọi tool get_weather để lấy thông tin rồi trả lời ngắn gọn bằng tiếng Việt."
        ),
    )


class WeatherExecutor(AgentExecutor):
    \"\"\"Bộ não xử lý mỗi yêu cầu. Framework gọi execute() khi có message mới.\"\"\"

    def __init__(self, agent):
        self.agent = agent

    async def execute(self, context: RequestContext, event_queue: EventQueue):
        # 1) Đọc câu hỏi người dùng
        user_input = context.get_user_input()
        task_id = context.task_id
        context_id = context.context_id

        # 2) "Phát thanh viên" báo trạng thái cho client
        updater = TaskUpdater(event_queue, task_id, context_id)
        await updater.start_work(
            message=updater.new_agent_message(
                parts=[Part(text="Đang kiểm tra thời tiết...")]
            )
        )

        # 3) Suy nghĩ: DeepAgent thật HOẶC mock brain
        if self.agent is not None:
            answer = await run_deep_agent(self.agent, user_input, thread_id=task_id)
        else:
            answer = self.mock_brain(user_input)

        # 4) Giao kết quả (artifact) và báo hoàn thành
        await updater.add_artifact(
            parts=[Part(text=answer)], name="response", last_chunk=True
        )
        await updater.complete()

    def mock_brain(self, query: str) -> str:
        \"\"\"Bộ não giả - không cần LLM, chỉ để học phần giao tiếp A2A.\"\"\"
        cities = {"hanoi": "Hà Nội", "hcmc": "TP.HCM", "danang": "Đà Nẵng", "hue": "Huế"}
        q = query.lower()
        for key, name in cities.items():
            if key in q:
                return f"[MOCK weather] {name}: 28°C, trời nắng nhẹ."
        return "[MOCK weather] 27°C, trời trong xanh."

    async def cancel(self, context: RequestContext, event_queue: EventQueue):
        updater = TaskUpdater(event_queue, context.task_id, context.context_id)
        await updater.cancel()


def create_app(host: str, port: int):
    \"\"\"Lắp ráp server: Agent Card + Request Handler + routes.\"\"\"
    # Agent Card = "danh thiếp số" của agent
    agent_card = AgentCard(
        name="Weather Agent",
        description="Chuyên gia thời tiết: trả lời câu hỏi về thời tiết theo thành phố.",
        provider=AgentProvider(organization="A2A Course", url="http://example.com"),
        version="1.0.0",
        capabilities=AgentCapabilities(streaming=True, push_notifications=False),
        default_input_modes=["text"],
        default_output_modes=["text", "task-status"],
        skills=[
            AgentSkill(
                id="weather",
                name="Weather lookup",
                description="Hỏi thời tiết của một thành phố.",
                tags=["weather"],
                examples=["Thời tiết Hà Nội thế nào?"],
                input_modes=["text"],
                output_modes=["text", "task-status"],
            )
        ],
        supported_interfaces=[
            AgentInterface(
                protocol_binding="JSONRPC",
                protocol_version="1.0",
                url=f"http://{host}:{port}/a2a/jsonrpc",
            )
        ],
    )

    request_handler = DefaultRequestHandler(
        agent_executor=WeatherExecutor(build_deep_agent()),
        task_store=InMemoryTaskStore(),
        agent_card=agent_card,
    )

    app = FastAPI(title=agent_card.name)
    add_a2a_routes_to_fastapi(
        app,
        agent_card_routes=create_agent_card_routes(agent_card=agent_card),
        jsonrpc_routes=create_jsonrpc_routes(
            request_handler=request_handler,
            rpc_url="/a2a/jsonrpc",
            enable_v0_3_compat=True,
        ),
        rest_routes=create_rest_routes(
            request_handler=request_handler,
            path_prefix="/a2a/rest",
            enable_v0_3_compat=True,
        ),
    )
    return app


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=41251)
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO)
    uvicorn.run(create_app(args.host, args.port), host=args.host, port=args.port)


if __name__ == "__main__":
    main()""")

md("""## 5.2 Agent 2 — News Agent (`news_agent.py`) 📰

Chạy ở cổng **41252**. Có tool `get_news(topic)`.

> 👀 **Thử thách nhỏ:** đối chiếu file này với `weather_agent.py` — bạn sẽ thấy **chỉ khác 3 chỗ**: tên tool, nội dung mock brain, và tên lớp/port. Phần khung A2A (executor, agent card, routes) **giống hệt**.
""")

code("""%%writefile {PROJECT_DIR}/news_agent.py
\"\"\"News Agent - trả lời tin tức theo chủ đề.\"\"\"
import argparse
import logging

import uvicorn
from fastapi import FastAPI

from a2a.server.agent_execution.agent_executor import AgentExecutor
from a2a.server.agent_execution.context import RequestContext
from a2a.server.events.event_queue import EventQueue
from a2a.server.request_handlers import DefaultRequestHandler
from a2a.server.routes import (
    add_a2a_routes_to_fastapi,
    create_agent_card_routes,
    create_jsonrpc_routes,
    create_rest_routes,
)
from a2a.server.tasks.inmemory_task_store import InMemoryTaskStore
from a2a.server.tasks.task_updater import TaskUpdater
from a2a.types import (
    AgentCapabilities,
    AgentCard,
    AgentInterface,
    AgentProvider,
    AgentSkill,
    Part,
)

from a2a_common import get_model, run_deep_agent

logger = logging.getLogger(__name__)


def build_deep_agent():
    \"\"\"Tạo DeepAgent làm "bộ não" thật. Chưa có API key -> None (dùng mock).\"\"\"
    model = get_model()
    if model is None:
        return None

    from deepagents import create_deep_agent
    from langchain.tools import tool

    @tool
    def get_news(topic: str) -> str:
        \"\"\"Trả về các dòng tít tin tức nổi bật về một chủ đề.\"\"\"
        topic = topic.strip().lower()
        headlines = {
            "công nghệ": [
                "AI thay đổi cách lập trình viên làm việc",
                "Ra mắt chip điện toán lượng tử mới",
            ],
            "kinh tế": [
                "GDP quý này tăng trưởng 6.5%",
                "Giá vàng lập đỉnh mới",
            ],
            "thể thao": [
                "Đội tuyển quốc gia giành chiến thắng 2-0",
                "Giải bóng đá mở màn sôi động",
            ],
        }
        for k, v in headlines.items():
            if k in topic:
                return "\\n".join(f"- {h}" for h in v)
        return f"- Tin nóng về {topic}\\n- Phân tích chuyên sâu về {topic}"

    return create_deep_agent(
        name="news_agent",
        model=model,
        tools=[get_news],
        system_prompt=(
            "Bạn là chuyên gia tin tức. Khi được hỏi về tin tức theo chủ đề, "
            "hãy gọi tool get_news rồi trả lời ngắn gọn bằng tiếng Việt."
        ),
    )


class NewsExecutor(AgentExecutor):
    def __init__(self, agent):
        self.agent = agent

    async def execute(self, context: RequestContext, event_queue: EventQueue):
        user_input = context.get_user_input()
        task_id = context.task_id
        context_id = context.context_id

        updater = TaskUpdater(event_queue, task_id, context_id)
        await updater.start_work(
            message=updater.new_agent_message(
                parts=[Part(text="Đang tìm tin tức...")]
            )
        )

        if self.agent is not None:
            answer = await run_deep_agent(self.agent, user_input, thread_id=task_id)
        else:
            answer = self.mock_brain(user_input)

        await updater.add_artifact(
            parts=[Part(text=answer)], name="response", last_chunk=True
        )
        await updater.complete()

    def mock_brain(self, query: str) -> str:
        q = query.lower()
        topics = {"công nghệ": "công nghệ", "tech": "công nghệ",
                  "kinh tế": "kinh tế", "thể thao": "thể thao"}
        for key, label in topics.items():
            if key in q:
                return (
                    f"[MOCK news] Tin nổi bật về {label}:\\n"
                    f"- Tiêu đề số 1 về {label}\\n"
                    f"- Tiêu đề số 2 về {label}"
                )
        return "[MOCK news] Tin nóng: Hôm nay thị trường khởi sắc, trời nắng đẹp."

    async def cancel(self, context: RequestContext, event_queue: EventQueue):
        updater = TaskUpdater(event_queue, context.task_id, context.context_id)
        await updater.cancel()


def create_app(host: str, port: int):
    agent_card = AgentCard(
        name="News Agent",
        description="Chuyên gia tin tức: trả lời các dòng tít tin tức theo chủ đề.",
        provider=AgentProvider(organization="A2A Course", url="http://example.com"),
        version="1.0.0",
        capabilities=AgentCapabilities(streaming=True, push_notifications=False),
        default_input_modes=["text"],
        default_output_modes=["text", "task-status"],
        skills=[
            AgentSkill(
                id="news",
                name="News lookup",
                description="Hỏi tin tức theo chủ đề.",
                tags=["news"],
                examples=["Tin tức công nghệ hôm nay?"],
                input_modes=["text"],
                output_modes=["text", "task-status"],
            )
        ],
        supported_interfaces=[
            AgentInterface(
                protocol_binding="JSONRPC",
                protocol_version="1.0",
                url=f"http://{host}:{port}/a2a/jsonrpc",
            )
        ],
    )

    request_handler = DefaultRequestHandler(
        agent_executor=NewsExecutor(build_deep_agent()),
        task_store=InMemoryTaskStore(),
        agent_card=agent_card,
    )

    app = FastAPI(title=agent_card.name)
    add_a2a_routes_to_fastapi(
        app,
        agent_card_routes=create_agent_card_routes(agent_card=agent_card),
        jsonrpc_routes=create_jsonrpc_routes(
            request_handler=request_handler,
            rpc_url="/a2a/jsonrpc",
            enable_v0_3_compat=True,
        ),
        rest_routes=create_rest_routes(
            request_handler=request_handler,
            path_prefix="/a2a/rest",
            enable_v0_3_compat=True,
        ),
    )
    return app


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=41252)
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO)
    uvicorn.run(create_app(args.host, args.port), host=args.host, port=args.port)


if __name__ == "__main__":
    main()""")

md("""## 5.3 Agent 3 — Currency Agent (`currency_agent.py`) 💱

Chạy ở cổng **41253**. Có tool `convert_currency(amount, from_ccy, to_ccy)`.
""")

code("""%%writefile {PROJECT_DIR}/currency_agent.py
\"\"\"Currency Agent - chuyển đổi tiền tệ.\"\"\"
import argparse
import logging
import re

import uvicorn
from fastapi import FastAPI

from a2a.server.agent_execution.agent_executor import AgentExecutor
from a2a.server.agent_execution.context import RequestContext
from a2a.server.events.event_queue import EventQueue
from a2a.server.request_handlers import DefaultRequestHandler
from a2a.server.routes import (
    add_a2a_routes_to_fastapi,
    create_agent_card_routes,
    create_jsonrpc_routes,
    create_rest_routes,
)
from a2a.server.tasks.inmemory_task_store import InMemoryTaskStore
from a2a.server.tasks.task_updater import TaskUpdater
from a2a.types import (
    AgentCapabilities,
    AgentCard,
    AgentInterface,
    AgentProvider,
    AgentSkill,
    Part,
)

from a2a_common import get_model, run_deep_agent

logger = logging.getLogger(__name__)

# Tỷ giá giả lập (đơn vị: 1 ngoại tệ = X VND)
RATES = {"USD": 24500, "EUR": 26500, "GBP": 31000, "JPY": 165, "VND": 1}


def build_deep_agent():
    \"\"\"Tạo DeepAgent làm "bộ não" thật. Chưa có API key -> None (dùng mock).\"\"\"
    model = get_model()
    if model is None:
        return None

    from deepagents import create_deep_agent
    from langchain.tools import tool

    @tool
    def convert_currency(amount: float, from_ccy: str, to_ccy: str) -> str:
        \"\"\"Chuyển một số tiền từ đơn vị tiền tệ này sang đơn vị khác.\"\"\"
        f = from_ccy.strip().upper()
        t = to_ccy.strip().upper()
        if f not in RATES or t not in RATES:
            return "Không tìm thấy tỷ giá cho cặp tiền này."
        result = amount * RATES[f] / RATES[t]
        return (
            f"{amount:,.0f} {f} = {result:,.0f} {t} "
            f"(tỷ giá 1 {f} = {RATES[f] / RATES[t]:,.2f} {t})"
        )

    return create_deep_agent(
        name="currency_agent",
        model=model,
        tools=[convert_currency],
        system_prompt=(
            "Bạn là chuyên gia tài chính. Khi được hỏi về chuyển đổi tiền tệ, "
            "hãy gọi tool convert_currency (nhớ tách số tiền và 2 đơn vị tiền) "
            "rồi trả lời ngắn gọn bằng tiếng Việt."
        ),
    )


class CurrencyExecutor(AgentExecutor):
    def __init__(self, agent):
        self.agent = agent

    async def execute(self, context: RequestContext, event_queue: EventQueue):
        user_input = context.get_user_input()
        task_id = context.task_id
        context_id = context.context_id

        updater = TaskUpdater(event_queue, task_id, context_id)
        await updater.start_work(
            message=updater.new_agent_message(
                parts=[Part(text="Đang tra tỷ giá...")]
            )
        )

        if self.agent is not None:
            answer = await run_deep_agent(self.agent, user_input, thread_id=task_id)
        else:
            answer = self.mock_brain(user_input)

        await updater.add_artifact(
            parts=[Part(text=answer)], name="response", last_chunk=True
        )
        await updater.complete()

    def mock_brain(self, query: str) -> str:
        \"\"\"Mock brain: bóc tách "số tiền + đơn vị" đơn giản bằng regex.\"\"\"
        m = re.search(r"(\\d+)\\s*(usd|vnd|eur|euro|gbp|jpy)", query.lower())
        if m:
            amount = float(m.group(1))
            ccy = m.group(2).upper()
            return f"[MOCK currency] {amount:,.0f} {ccy} = {amount * RATES[ccy]:,.0f} VND (tỷ giá giả lập)."
        return "[MOCK currency] Ví dụ: hãy hỏi 'đổi 100 USD sang VND'."

    async def cancel(self, context: RequestContext, event_queue: EventQueue):
        updater = TaskUpdater(event_queue, context.task_id, context.context_id)
        await updater.cancel()


def create_app(host: str, port: int):
    agent_card = AgentCard(
        name="Currency Agent",
        description="Chuyên gia tài chính: chuyển đổi tiền tệ giữa các đơn vị.",
        provider=AgentProvider(organization="A2A Course", url="http://example.com"),
        version="1.0.0",
        capabilities=AgentCapabilities(streaming=True, push_notifications=False),
        default_input_modes=["text"],
        default_output_modes=["text", "task-status"],
        skills=[
            AgentSkill(
                id="currency",
                name="Currency conversion",
                description="Đổi tiền giữa các đơn vị tiền tệ.",
                tags=["currency"],
                examples=["100 USD bằng bao nhiêu VND?"],
                input_modes=["text"],
                output_modes=["text", "task-status"],
            )
        ],
        supported_interfaces=[
            AgentInterface(
                protocol_binding="JSONRPC",
                protocol_version="1.0",
                url=f"http://{host}:{port}/a2a/jsonrpc",
            )
        ],
    )

    request_handler = DefaultRequestHandler(
        agent_executor=CurrencyExecutor(build_deep_agent()),
        task_store=InMemoryTaskStore(),
        agent_card=agent_card,
    )

    app = FastAPI(title=agent_card.name)
    add_a2a_routes_to_fastapi(
        app,
        agent_card_routes=create_agent_card_routes(agent_card=agent_card),
        jsonrpc_routes=create_jsonrpc_routes(
            request_handler=request_handler,
            rpc_url="/a2a/jsonrpc",
            enable_v0_3_compat=True,
        ),
        rest_routes=create_rest_routes(
            request_handler=request_handler,
            path_prefix="/a2a/rest",
            enable_v0_3_compat=True,
        ),
    )
    return app


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=41253)
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO)
    uvicorn.run(create_app(args.host, args.port), host=args.host, port=args.port)


if __name__ == "__main__":
    main()""")

# =====================================================================
# CHƯƠNG 6 - CHẠY SERVER
# =====================================================================
md("""# Chương 6 — Khởi động các server 🚀

### Vì sao dùng `subprocess`?

Mỗi agent là một **dịch vụ độc lập** (file `.py` riêng). Trong notebook, ta không chạy chúng trực tiếp trong cùng tiến trình (sẽ "kẹt" vì server chạy vô hạn). Thay vào đó ta **mở một tiến trình con** cho mỗi agent — giống như mở 4 "cửa hàng" riêng biệt trên 4 con phố khác nhau.

Hàm `start_server()` dưới đây:

1. Mở tiến trình `python <file>.py --port <port>` (dùng chính Python của kernel).
2. Ghi log ra file `<tên>.log` (để tra cứu khi gặp lỗi).
3. Lưu lại "điều khiển" tiến trình để sau này tắt được.
""")

code("""import subprocess
import sys

PROCESSES = []  # danh sách "điều khiển" các server đang chạy


def start_server(name, port):
    \"\"\"Mở một agent server trong tiến trình con.\"\"\"
    script = os.path.join(PROJECT_DIR, f"{name}.py")
    log_path = os.path.join(PROJECT_DIR, f"{name}.log")
    log_file = open(log_path, "w", encoding="utf-8")
    proc = subprocess.Popen(
        [sys.executable, script, "--port", str(port)],
        stdout=log_file,
        stderr=subprocess.STDOUT,
        cwd=PROJECT_DIR,
    )
    PROCESSES.append(proc)
    print(f"Đã khởi động {name} (pid={proc.pid}) -> log: {os.path.basename(log_path)}")
    return proc


def stop_all_servers():
    \"\"\"Tắt tất cả server (gọi khi kết thúc buổi học).\"\"\"
    for proc in PROCESSES:
        proc.terminate()
    for proc in PROCESSES:
        try:
            proc.wait(timeout=5)
        except Exception:
            proc.kill()
    PROCESSES.clear()
    print("Đã dừng tất cả server.")""")

code("""# Khởi động 3 worker agents
start_server("weather_agent", 41251)
start_server("news_agent", 41252)
start_server("currency_agent", 41253)""")

md("""### ⏳ Chờ server sẵn sàng

Server cần vài giây để "dọn hàng" (import thư viện, mở cổng). Ta chờ tới khi đọc được **Agent Card** — giống như chờ cửa hàng treo biển "đã mở cửa" 🏪.
""")

code("""from a2a_common import wait_for_server

# Chờ cả 3 worker sẵn sàng
for name, port in [("weather", 41251), ("news", 41252), ("currency", 41253)]:
    url = f"http://127.0.0.1:{port}"
    ok = await wait_for_server(url)
    print(f"{name:10s} {url:35s} -> {'SẴN SÀNG ✅' if ok else 'LỖI ❌'}")""")

# =====================================================================
# CHƯƠNG 7 - A2A CLIENT
# =====================================================================
md("""# Chương 7 — A2A Client: gọi agent từ xa 📞

Giờ ta đóng vai **User** để gọi từng worker. Hàm `call_agent()` trong `a2a_common.py` chính là A2A Client.

### Điều gì xảy ra khi gọi?

```mermaid
sequenceDiagram
    participant N as Notebook (Client)
    participant W as Weather Agent (Server)
    N->>W: GET /.well-known/agent-card.json (đọc danh thiếp)
    W-->>N: AgentCard
    N->>W: SendMessage("Thời tiết Hà Nội?")
    W-->>N: status: submitted
    W-->>N: status: working
    W-->>N: artifact: "Hà Nội 28°C..."
    W-->>N: status: completed
```

> 💡 Chú ý dòng `[status] ...` in ra: đó là **TaskUpdater bên server "phát thanh"** về cho client. Client nhận được sự kiện qua **stream** (SSE). Đây là sức mạnh của A2A: ta luôn biết task đang ở đâu trong vòng đời.
""")

code("""# Gọi trực tiếp Weather Agent
ket_qua = await call_agent("http://127.0.0.1:41251", "Thời tiết Hà Nội hôm nay thế nào?")
print()
print("=== KẾT QUẢ WEATHER ===")
print(ket_qua)""")

code("""# Gọi trực tiếp News Agent và Currency Agent
print("--- NEWS ---")
print(await call_agent("http://127.0.0.1:41252", "Cho tôi tin tức công nghệ hôm nay"))
print()
print("--- CURRENCY ---")
print(await call_agent("http://127.0.0.1:41253", "100 USD bằng bao nhiêu VND?"))""")

# =====================================================================
# CHƯƠNG 8 - ORCHESTRATOR
# =====================================================================
md("""# Chương 8 — Orchestrator: "đội trưởng" 🧑‍💼

Đến đây ta đã có 3 chuyên gia độc lập. Vấn đề: **ai là người nghe người dùng và quyết định gọi ai?**

Đó chính là **orchestrator** — một DeepAgent đặc biệt:

- Nó là **A2A Server** (để người dùng nói chuyện với nó qua A2A).
- Bên trong là **DeepAgent** với 3 tools: `ask_weather`, `ask_news`, `ask_currency`.
- Mỗi tool, khi được gọi, sẽ dùng **A2A Client** (`call_agent`) để gọi worker tương ứng ở xa.

```mermaid
sequenceDiagram
    participant U as 👤 User
    participant O as 🧑‍💼 Orchestrator (DeepAgent)
    participant W as 🌤️ Weather Agent
    participant C as 💱 Currency Agent
    U->>O: "Thời tiết HN thế nào và 100 USD = ?"
    O->>O: DeepAgent quyết định gọi tool nào
    O->>W: call_agent(weather) - A2A
    W-->>O: "Hà Nội 28°C..."
    O->>C: call_agent(currency) - A2A
    C-->>O: "100 USD = 2.450.000 VND"
    O-->>U: Tổng hợp thành 1 câu trả lời
```

> 🎯 **Bản chất quan trọng:** Orchestrator **không trực tiếp tính** thời tiết hay tỷ giá. Nó **hỏi** các chuyên gia qua A2A rồi gom kết quả. Đúng như một người quản lý giỏi: *không tự làm, mà biết giao đúng người*.

> 🔁 **Vòng lặp "vừa Server vừa Client":** Orchestrator nhận yêu cầu với vai **Server**, rồi gọi worker với vai **Client**. Vai trò đảo nhau tuỳ hướng nói chuyện.
""")

code("""%%writefile {PROJECT_DIR}/orchestrator_agent.py
\"\"\"Orchestrator Agent - điều phối 3 worker agents qua giao thức A2A.

Vừa là A2A Server (nhận yêu cầu từ User) vừa là A2A Client (gọi worker).
\"\"\"
import argparse
import logging
import os

import uvicorn
from fastapi import FastAPI

from a2a.server.agent_execution.agent_executor import AgentExecutor
from a2a.server.agent_execution.context import RequestContext
from a2a.server.events.event_queue import EventQueue
from a2a.server.request_handlers import DefaultRequestHandler
from a2a.server.routes import (
    add_a2a_routes_to_fastapi,
    create_agent_card_routes,
    create_jsonrpc_routes,
    create_rest_routes,
)
from a2a.server.tasks.inmemory_task_store import InMemoryTaskStore
from a2a.server.tasks.task_updater import TaskUpdater
from a2a.types import (
    AgentCapabilities,
    AgentCard,
    AgentInterface,
    AgentProvider,
    AgentSkill,
    Part,
    Task,
    TaskState,
    TaskStatus,
)

from a2a_common import call_agent, get_model, run_deep_agent

logger = logging.getLogger(__name__)

# Địa chỉ 3 worker (có thể đổi qua biến môi trường)
WEATHER_URL = os.environ.get("A2A_WEATHER_URL", "http://127.0.0.1:41251")
NEWS_URL = os.environ.get("A2A_NEWS_URL", "http://127.0.0.1:41252")
CURRENCY_URL = os.environ.get("A2A_CURRENCY_URL", "http://127.0.0.1:41253")


def build_deep_agent():
    \"\"\"DeepAgent làm "bộ não điều phối". Chưa có API key -> None (dùng mock).\"\"\"
    model = get_model()
    if model is None:
        return None

    from deepagents import create_deep_agent
    from langchain.tools import tool

    # Mỗi tool = một "đường dây điện thoại" tới một worker qua A2A
    @tool
    async def ask_weather(query: str) -> str:
        \"\"\"Gửi câu hỏi về thời tiết cho Weather Agent.\"\"\"
        return await call_agent(WEATHER_URL, query, verbose=False)

    @tool
    async def ask_news(query: str) -> str:
        \"\"\"Gửi câu hỏi về tin tức cho News Agent.\"\"\"
        return await call_agent(NEWS_URL, query, verbose=False)

    @tool
    async def ask_currency(query: str) -> str:
        \"\"\"Gửi câu hỏi về chuyển đổi tiền tệ cho Currency Agent.\"\"\"
        return await call_agent(CURRENCY_URL, query, verbose=False)

    return create_deep_agent(
        name="orchestrator",
        model=model,
        tools=[ask_weather, ask_news, ask_currency],
        system_prompt=(
            "Bạn là đội trưởng điều phối. Quy tắc:\\n"
            "- Hỏi về thời tiết -> gọi ask_weather\\n"
            "- Hỏi về tin tức -> gọi ask_news\\n"
            "- Hỏi về tiền tệ/đổi tiền -> gọi ask_currency\\n"
            "- Yêu cầu phức tạp -> gọi NHIỀU tool và tổng hợp.\\n"
            "Cuối cùng hãy trả lời rõ ràng, thân thiện bằng tiếng Việt."
        ),
    )


class OrchestratorExecutor(AgentExecutor):
    def __init__(self, agent):
        self.agent = agent

    async def execute(self, context: RequestContext, event_queue: EventQueue):
        user_input = context.get_user_input()
        task_id = context.task_id
        context_id = context.context_id

        # BẮT BUỘC: gửi Task ban đầu (submitted) TRƯỚC các status update
        await event_queue.enqueue_event(
            Task(
                id=task_id,
                context_id=context_id,
                status=TaskStatus(state=TaskState.TASK_STATE_SUBMITTED),
                history=[context.message],
            )
        )

        updater = TaskUpdater(event_queue, task_id, context_id)
        await updater.start_work(
            message=updater.new_agent_message(
                parts=[Part(text="Đang điều phối các chuyên gia...")]
            )
        )

        if self.agent is not None:
            answer = await run_deep_agent(self.agent, user_input, thread_id=task_id)
        else:
            answer = await self.mock_orchestrate(user_input)

        await updater.add_artifact(
            parts=[Part(text=answer)], name="response", last_chunk=True
        )
        await updater.complete()

    async def mock_orchestrate(self, query: str) -> str:
        \"\"\"Mock brain: vẫn THỰC SỰ gọi các worker qua A2A (chỉ thiếu phần "suy luận").\"\"\"
        q = query.lower()
        tasks = []
        if any(w in q for w in ["thời tiết", "weather", "nhiệt độ", "trời"]):
            tasks.append(("Weather", WEATHER_URL))
        if any(w in q for w in ["tin tức", "news", "bản tin"]):
            tasks.append(("News", NEWS_URL))
        if any(w in q for w in ["tiền", "đổi", "usd", "vnd", "eur", "gbp", "jpy", "giá"]):
            tasks.append(("Currency", CURRENCY_URL))

        if not tasks:
            return (
                "Tôi là orchestrator. Tôi có thể giúp bạn về: thời tiết, tin tức, "
                "chuyển đổi tiền tệ. Hãy thử hỏi: 'Thời tiết Hà Nội thế nào?'"
            )

        results = []
        for name, url in tasks:
            result = await call_agent(url, query, verbose=False)
            results.append(f"[{name}]\\n{result}")
        return "\\n\\n".join(results)

    async def cancel(self, context: RequestContext, event_queue: EventQueue):
        updater = TaskUpdater(event_queue, context.task_id, context.context_id)
        await updater.cancel()


def create_app(host: str, port: int):
    agent_card = AgentCard(
        name="Orchestrator Agent",
        description="Điều phối viên: nghe yêu cầu, gọi các chuyên gia (weather/news/currency) và tổng hợp.",
        provider=AgentProvider(organization="A2A Course", url="http://example.com"),
        version="1.0.0",
        capabilities=AgentCapabilities(streaming=True, push_notifications=False),
        default_input_modes=["text"],
        default_output_modes=["text", "task-status"],
        skills=[
            AgentSkill(
                id="orchestrate",
                name="Orchestrate specialists",
                description="Điều phối các agent chuyên môn.",
                tags=["orchestration"],
                examples=["Thời tiết Hà Nội và giá USD hôm nay?"],
                input_modes=["text"],
                output_modes=["text", "task-status"],
            )
        ],
        supported_interfaces=[
            AgentInterface(
                protocol_binding="JSONRPC",
                protocol_version="1.0",
                url=f"http://{host}:{port}/a2a/jsonrpc",
            )
        ],
    )

    request_handler = DefaultRequestHandler(
        agent_executor=OrchestratorExecutor(build_deep_agent()),
        task_store=InMemoryTaskStore(),
        agent_card=agent_card,
    )

    app = FastAPI(title=agent_card.name)
    add_a2a_routes_to_fastapi(
        app,
        agent_card_routes=create_agent_card_routes(agent_card=agent_card),
        jsonrpc_routes=create_jsonrpc_routes(
            request_handler=request_handler,
            rpc_url="/a2a/jsonrpc",
            enable_v0_3_compat=True,
        ),
        rest_routes=create_rest_routes(
            request_handler=request_handler,
            path_prefix="/a2a/rest",
            enable_v0_3_compat=True,
        ),
    )
    return app


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=41241)
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO)
    uvicorn.run(create_app(args.host, args.port), host=args.host, port=args.port)


if __name__ == "__main__":
    main()""")

code("""# Khởi động orchestrator (cổng 41241) và chờ sẵn sàng
start_server("orchestrator_agent", 41241)
await wait_for_server("http://127.0.0.1:41241")
print("Orchestrator SẴN SÀNG ✅")""")

# =====================================================================
# CHƯƠNG 9 - DEMO END-TO-END
# =====================================================================
md("""# Chương 9 — Demo End-to-End: gọi orchestrator 🎬

Bây giờ mọi thứ đã nối mạch: **User → Orchestrator → (A2A) → 3 Workers**.

Hãy chú ý:
- Dòng `[status]` in ra là **orchestrator** báo tiến trình.
- Câu trả lời cuối là **kết quả tổng hợp** — orchestrator đã âm thầm gọi các worker ở tầng dưới.
""")

code("""# Demo 1: câu hỏi đơn giản -> orchestrator gọi đúng 1 chuyên gia
ket_qua = await call_agent("http://127.0.0.1:41241", "Thời tiết Đà Nẵng thế nào?")
print()
print("=== TRẢ LỜI CỦA ORCHESTRATOR ===")
print(ket_qua)""")

code("""# Demo 2: câu hỏi TỔNG HỢP -> orchestrator gọi NHIỀU chuyên gia
ket_qua = await call_agent(
    "http://127.0.0.1:41241",
    "Hôm nay thời tiết Hà Nội thế nào? Và 100 USD đổi được bao nhiêu VND?"
)
print()
print("=== TRẢ LỜI CỦA ORCHESTRATOR ===")
print(ket_qua)""")

code("""# Demo 3: xem "danh thiếp" (Agent Card) của orchestrator - agent khai báo mình là ai
import httpx

async with httpx.AsyncClient() as client:
    r = await client.get("http://127.0.0.1:41241/.well-known/agent-card.json")
    card = r.json()

print("Tên:", card.get("name"))
print("Mô tả:", card.get("description"))
print("Kỹ năng:", [s["name"] for s in card.get("skills", [])])
print("Địa chỉ liên lạc:", [i["url"] for i in card.get("supported_interfaces", [])])""")

# =====================================================================
# CHƯƠNG 10 - TỔNG KẾT
# =====================================================================
md("""# Chương 10 — Tổng kết 🏁

## Sơ đồ toàn cảnh

```mermaid
graph TD
    U([👤 User]) -->|A2A| O
    subgraph O[🧑‍💼 Orchestrator - port 41241]
        DA[DeepAgent<br/>tools: ask_weather/news/currency]
        EX[AgentExecutor]
        DA --> EX
    end
    O -->|A2A Client| W
    O -->|A2A Client| N
    O -->|A2A Client| C
    W[🌤️ Weather - 41251<br/>DeepAgent + tool get_weather]
    N[📰 News - 41252<br/>DeepAgent + tool get_news]
    C[💱 Currency - 41253<br/>DeepAgent + tool convert_currency]
```

## Bạn đã học được gì?

| Khái niệm | Bạn làm được |
|---|---|
| Agent Card | Khai báo "danh thiếp số" cho agent |
| AgentExecutor | Viết bộ não xử lý yêu cầu (`execute`/`cancel`) |
| TaskUpdater | Báo tiến trình & kết quả cho client |
| A2A Client | Gọi agent từ xa qua `call_agent()` |
| Orchestrator | DeepAgent vừa là Server vừa là Client, điều phối worker |

## A2A vs "subagents" trong DeepAgents — khác gì? 🤔

Bạn đã quen với `subagents` trong DeepAgents (agent cha gọi agent con). Hãy so sánh:

| Tiêu chí | Subagents (DeepAgents) | A2A |
|---|---|---|
| Phạm vi | **Trong cùng một tiến trình** | **Qua mạng, giữa các dịch vụ** |
| Framework | Bắt buộc cùng DeepAgents | Bất kỳ framework nào (chuẩn mở) |
| Nơi chạy | Cùng máy/cùng app | Máy khác nhau, công ty khác nhau |
| Giao thức | Gọi hàm nội bộ | HTTP + JSON-RPC |
| Độ tách biệt | Thấp (chung bộ nhớ) | Cao (opaque, không lộ nội bộ) |

> 💡 **Quy tắc chọn:** Việc trong một app → dùng subagents. Việc giữa các app/dịch vụ độc lập → dùng A2A. Trong thực tế người ta **kết hợp cả hai**: DeepAgents lo việc bên trong, A2A lo việc bên ngoài.

## Tài liệu tham khảo trong `refs/`

- `refs/A2A/docs/specification.md` — đặc tả giao thức A2A 1.0
- `refs/A2A/docs/topics/key-concepts.md` — khái niệm cốt lõi
- `refs/A2A/docs/topics/life-of-a-task.md` — vòng đời Task
- `refs/a2a-python/samples/hello_world_agent.py` — mẫu server chính thức
- `refs/a2a-python/samples/cli.py` — mẫu client chính thức

## Bài tập về nhà 🏠

1. **Đọc thêm:** mở `refs/a2a-python/samples/hello_world_agent.py` và đối chiếu từng dòng với `weather_agent.py` mà bạn vừa viết. Ghi ra 3 điểm giống và 3 điểm khác.
2. **Thêm agent thứ 4:** viết một `translate_agent.py` (chuyên dịch thuật) rồi nối vào orchestrator (thêm tool `ask_translate`). Nhớ chọn port mới!
3. **Bật DeepAgent thật:** set API key (xem Chương 3) rồi chạy lại từ đầu. So sánh câu trả lời MOCK và thật.
4. **Nâng cao:** đổi worker sang dùng `InMemoryStore`/checkpointer của DeepAgents để worker có **trí nhớ** qua nhiều lượt hỏi.
""")

# =====================================================================
# DỌN DẸP
# =====================================================================
md("""# 🧹 Dọn dẹp (chạy cuối buổi học)

Cell này tắt toàn bộ server để giải phóng cổng. Chạy lại từ đầu khi muốn học lại.
""")

code("""stop_all_servers()""")

# =====================================================================
# GHI FILE
# =====================================================================
nb = {
    "cells": CELLS,
    "metadata": {
        "kernelspec": {
            "display_name": "Python 3.14 (A2A Course)",
            "language": "python",
            "name": "a2a-course",
        },
        "language_info": {"name": "python", "version": "3.14.0"},
    },
    "nbformat": 4,
    "nbformat_minor": 5,
}

out = r"c:\Users\tamtt.OFFICEVNPAY\Desktop\A2A\A2A_MultiAgent_Notebook.ipynb"
with open(out, "w", encoding="utf-8") as f:
    json.dump(nb, f, ensure_ascii=False, indent=1)

print(f"Đã tạo notebook: {out}")
print(f"Số cell: {len(CELLS)}")
