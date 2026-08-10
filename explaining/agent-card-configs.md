# 🪪 Agent Card — Giải thích từng config, dùng để làm gì & khi nào dùng

> File này giải thích **chi tiết từng trường (config)** của `AgentCard` trong giao thức A2A.
> Mục tiêu: **học sinh cấp 3 cũng hiểu** — ngôn ngữ đơn giản, có ví von, có ví dụ thật.
> Đối chiếu với notebook `A2A_MultiAgent_Notebook.ipynb` và code trong `my_a2a_system/`.

---

## 1. Agent Card là gì? (nhìn nhanh)

**Agent Card = "Danh thiếp số" của một agent.** 🪪

Giống như danh thiếp giấy in *tên, chức danh, số điện thoại, địa chỉ công ty* — Agent Card cho các agent khác (và con người) biết:

| Thông tin trên danh thiếp thật | Thông tin trên Agent Card |
|---|---|
| Tên, chức danh | `name`, `description` |
| Công ty | `provider` |
| Số điện thoại / địa chỉ liên hệ | `supported_interfaces` (URL + giao thức) |
| "Tôi làm được gì" | `skills` |
| "Tôi có cần hẹn trước / bảo mật không" | `capabilities`, `security_schemes` |

Agent Card được đặt tại đường dẫn chuẩn:
```
http://<địa-chỉ-agent>/.well-known/agent-card.json
```
Bất kỳ client nào cũng biết **vào đúng chỗ đó để đọc danh thiếp** — đó là cơ chế **Agent Discovery** (khám phá agent).

> 📌 Trong notebook, hàm `create_client(base_url)` chính là "đọc danh thiếp rồi chỉnh điện thoại cho đúng tần số" trước khi gọi agent.

---

## 2. Ví dụ hoàn chỉnh (xem trước toàn cảnh)

Đây là **Agent Card của Weather Agent** trong khóa học, đầy đủ các trường — hãy để ý cách nó "khai báo" mình là ai và giao tiếp thế nào:

```json
{
  "name": "Weather Agent",
  "description": "Chuyên gia thời tiết: trả lời câu hỏi về thời tiết theo thành phố.",
  "url": "",
  "provider": {
    "organization": "A2A Course",
    "url": "http://example.com"
  },
  "version": "1.0.0",
  "documentationUrl": "https://example.com/docs/weather-agent",
  "iconUrl": "https://example.com/icon.png",
  "capabilities": {
    "streaming": true,
    "pushNotifications": false,
    "extensions": [],
    "extendedAgentCard": false
  },
  "defaultInputModes": ["text"],
  "defaultOutputModes": ["text", "task-status"],
  "skills": [
    {
      "id": "weather",
      "name": "Weather lookup",
      "description": "Hỏi thời tiết của một thành phố.",
      "tags": ["weather"],
      "examples": ["Thời tiết Hà Nội thế nào?"],
      "inputModes": ["text"],
      "outputModes": ["text", "task-status"]
    }
  ],
  "supportedInterfaces": [
    {
      "url": "http://127.0.0.1:41251/a2a/jsonrpc",
      "protocolBinding": "JSONRPC",
      "protocolVersion": "1.0"
    }
  ],
  "securitySchemes": {},
  "securityRequirements": []
}
```

> ⚠️ **Lưu ý cách đặt tên:** Trong **JSON giao thức** (gửi trên mạng) tên trường viết **camelCase** (`supportedInterfaces`, `pushNotifications`...). Trong **Python SDK** (`a2a-sdk`) tên trường viết **snake_case** (`supported_interfaces`, `push_notifications`...). Cùng một thứ, hai cách viết — đừng hoang mang!

| JSON (trên mạng) | Python (trong code) |
|---|---|
| `supportedInterfaces` | `supported_interfaces` |
| `protocolBinding` | `protocol_binding` |
| `pushNotifications` | `push_notifications` |
| `documentationUrl` | `documentation_url` |
| `defaultInputModes` | `default_input_modes` |

---

## 3. Giải thích từng trường của `AgentCard`

> Đánh dấu: 🔴 **Bắt buộc** (không có thì "danh thiếp" không hợp lệ) • 🟢 **Tùy chọn** (có thì tốt, thiếu cũng chạy được).

### Nhóm A — Danh tính (agent là ai)

---

#### 🔴 `name` — Tên agent

- **Dùng để làm gì:** Để con người & agent khác **gọi đúng tên**, nhận diện nhanh.
- **Khi nào dùng:** Luôn dùng. Ngắn gọn, dễ hiểu.
- **Ví dụ:**
  ```python
  AgentCard(name="Weather Agent", ...)
  ```

---

#### 🔴 `description` — Mô tả agent

- **Dùng để làm gì:** Nói rõ **agent làm được gì**, giúp:
  1. Con người đọc menu trước khi gọi.
  2. **Agent khác (đặc biệt là orchestrator/LLM) đọc để quyết định**: "Tôi nên gọi agent này hay không?".
- **Khi nào dùng:** Luôn dùng. Viết rõ ràng, có từ khóa.
- **Ví dụ:**
  ```python
  description="Chuyên gia thời tiết: trả lời câu hỏi về thời tiết theo thành phố."
  ```

> 💡 Mẹo: Mô tả càng "giàu từ khóa" thì LLM/orchestrator càng dễ chọn đúng agent. Nếu bạn viết `description="Trả lời mọi thứ"` thì agent khác chẳng biết khi nào nên gọi bạn.

---

#### 🟢 `provider` — Nhà cung cấp

- **Dùng để làm gì:** Khai báo **công ty/tổ chức** đứng sau agent, kèm website. Giống phần "Công ty" trên danh thiếp.
- **Khi nào dùng:** Dùng khi agent thuộc về một tổ chức cụ thể (công ty, đội nhóm). Agent cá nhân học tập có thể bỏ qua.
- **Ví dụ:**
  ```python
  provider=AgentProvider(organization="A2A Course", url="http://example.com")
  ```

---

#### 🔴 `version` — Phiên bản agent

- **Dùng để làm gì:** Cho biết agent đang ở phiên bản nào (dùng quy ước **SemVer**: `MAJOR.MINOR.PATCH`). Client dùng để: biết thông tin đã đổi chưa (cache), chọn phiên bản phù hợp.
- **Khi nào dùng:** Luôn dùng. **Mỗi khi đổi khả năng → tăng version**, để client không dùng thông tin cũ.
- **Ví dụ:** `version="1.0.0"` → khi thêm skill mới thành `version="1.1.0"`.

---

#### 🟢 `documentation_url` — Link tài liệu

- **Dùng để làm gì:** Trỏ tới trang tài liệu hướng dẫn chi tiết hơn.
- **Khi nào dùng:** Agent phức tạp, cần hướng dẫn sử dụng. Agent đơn giản có thể bỏ qua.
- **Ví dụ:** `documentation_url="https://example.com/docs/weather-agent"`

---

#### 🟢 `icon_url` — Link ảnh đại diện

- **Dùng để làm gì:** Hiện logo/ảnh khi agent xuất hiện trong UI, registry, marketplace.
- **Khi nào dùng:** Khi agent được hiển thị trong giao diện người dùng. Không ảnh hưởng giao tiếp.

---

### Nhóm B — Kết nối (nói chuyện với agent qua đâu)

---

#### 🔴 `supported_interfaces` — Danh sách "đường dây" liên lạc (quan trọng nhất!)

Mỗi phần tử là một `AgentInterface`. Client đọc danh sách này để biết **gọi vào URL nào, bằng giao thức gì**.

| Field của `AgentInterface` | Dùng để làm gì |
|---|---|
| 🔴 `url` | Địa chỉ endpoint (ví dụ `http://127.0.0.1:41251/a2a/jsonrpc`) |
| 🔴 `protocol_binding` | Giao thức: `"JSONRPC"`, `"GRPC"`, `"HTTP+JSON"` |
| 🔴 `protocol_version` | Phiên bản A2A: `"1.0"` (hiện tại), `"0.3"` (tương thích cũ) |
| 🟢 `tenant` | Cờ "phân luồng": khi **nhiều agent dùng chung một endpoint**, client gửi giá trị này để server biết đường định tuyến tới đúng agent |

- **Khi nào dùng:** Luôn dùng. Có thể khai **nhiều interface** để phục vụ nhiều giao thức.
- **Thứ tự quan trọng!** Phần tử **đầu tiên được ưu tiên nhất** — client sẽ thử theo thứ tự.
- **Ví dụ** — agent vừa có JSON-RPC vừa có REST:
  ```python
  supported_interfaces=[
      AgentInterface(
          protocol_binding="JSONRPC",
          protocol_version="1.0",
          url=f"http://{host}:{port}/a2a/jsonrpc",
      ),
      AgentInterface(
          protocol_binding="HTTP+JSON",
          protocol_version="1.0",
          url=f"http://{host}:{port}/a2a/rest",
      ),
  ]
  ```
- **Ví dụ `tenant`** — hai agent "phòng A" và "phòng B" dùng chung một server:
  ```python
  AgentInterface(
      protocol_binding="JSONRPC",
      protocol_version="1.0",
      url="https://công-ty.com/a2a",
      tenant="weather-branch",
  )
  ```

> 💡 Trong khóa học, SDK tự động chọn giao thức khớp với client (mặc định JSON-RPC), nên bạn chỉ cần khai `protocol_binding="JSONRPC"` là đủ.

---

### Nhóm C — Khả năng (capabilities)

`capabilities` là một đối tượng `AgentCapabilities` — **"tôi có những tính năng nâng cao nào?"**. Client đọc trước để biết nên dùng cách giao tiếp nào, tránh gọi thứ không được hỗ trợ.

| Field | Dùng để làm gì | Khi nào dùng = `true` |
|---|---|---|
| 🟢 `streaming` | Agent **đẩy kết quả từng phần** về client theo thời gian thực (SSE) thay vì trả nguyên cục | Agent xử lý lâu, muốn client thấy tiến trình (như **TaskUpdater báo "đang làm..."**) |
| 🟢 `push_notifications` | Agent chủ động **gửi thông báo** tới webhook của client khi task cập nhật | Task rất lâu, client không thể chờ giữ kết nối |
| 🟢 `extended_agent_card` | Agent có **danh thiếp mở rộng** (nhiều chi tiết hơn) chỉ hiện **sau khi client xác thực** | Có thông tin nhạy cảm, không muốn công khai |
| 🟢 `extensions` | Khai báo **phần mở rộng** ngoài chuẩn A2A | Cần tính năng riêng, hoặc dùng extension của cộng đồng |

- **Ví dụ streaming:**
  ```python
  capabilities=AgentCapabilities(streaming=True, push_notifications=False)
  ```
- **Ví dụ extensions** (khai extension "trích dẫn nguồn"):
  ```python
  capabilities=AgentCapabilities(
      streaming=True,
      push_notifications=False,
      extensions=[
          AgentExtension(
              uri="https://standards.org/extensions/citations/v1",
              description="Cung cấp định dạng trích dẫn và kiểm chứng nguồn",
              required=False,   # client không hiểu extension này vẫn gọi được
          )
      ],
  )
  ```
  > `required=True` nghĩa là **bắt buộc**: client không hỗ trợ extension đó thì server **từ chối** làm việc.

---

### Nhóm D — Nội dung trao đổi (content modes + skills)

---

#### 🔴 `default_input_modes` & `default_output_modes` — Kiểu nội dung nhận/trả

- **Dùng để làm gì:** Khai báo **loại nội dung (media type)** agent nhận vào và trả ra.
- **Khi nào dùng:** Luôn dùng. Thường là `["text"]` cho agent chat; thêm `image`, `audio`, `file` khi agent xử lý đa phương tiện.
- **Ví dụ:**
  ```python
  default_input_modes=["text"],
  default_output_modes=["text", "task-status"],
  ```
  > `task-status` là kiểu đặc biệt của A2A: agent trả về **trạng thái của Task**, không chỉ nội dung.

---

#### 🔴 `skills` — Danh sách kỹ năng

Mỗi kỹ năng là một `AgentSkill`. Đây là "bảng giá dịch vụ" — **điều quan trọng nhất để agent khác biết gọi bạn để làm gì**.

| Field của `AgentSkill` | Dùng để làm gì |
|---|---|
| 🔴 `id` | Mã định danh duy nhất của kỹ năng (ví dụ `"weather"`) |
| 🔴 `name` | Tên hiển thị |
| 🔴 `description` | Mô tả kỹ năng (LLM đọc cái này để quyết định gọi) |
| 🔴 `tags` | Từ khóa tìm kiếm (ví dụ `["weather"]`) |
| 🟢 `examples` | Ví dụ câu hỏi mà kỹ năng xử lý được (rất hữu ích cho LLM) |
| 🟢 `input_modes` / `output_modes` | Ghi đè kiểu nội dung riêng cho kỹ năng này (nếu khác với mặc định) |
| 🟢 `security_requirements` | Kỹ năng này có yêu cầu bảo mật riêng không |

- **Ví dụ:**
  ```python
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
  ]
  ```

> 🎯 **Mẹo vàng cho `examples`:** Orchestrator (DeepAgent) thường đọc `examples` để "bắt chước" cách đặt câu hỏi đúng. Thêm ví dụ thật cụ thể → tỉ lệ gọi đúng cao hơn rất nhiều.

---

### Nhóm E — Bảo mật (security)

A2A **không tự định nghĩa cách xác thực** mà dựa vào chuẩn web (giống OpenAPI). Agent khai báo trong card để client biết phải "xin giấy phép" kiểu gì.

---

#### 🟢 `security_schemes` — Định nghĩa các cách xác thực

Là một **map** (từ điển): tên scheme → định nghĩa chi tiết. Có 5 kiểu chính:

| Kiểu | Dùng khi nào | Ví dụ |
|---|---|---|
| `APIKeySecurityScheme` | Gửi **API key** (header/query/cookie) | `location="header", name="X-API-Key"` |
| `HTTPAuthSecurityScheme` | Dùng **HTTP Basic / Bearer token** | `scheme="bearer"` |
| `OAuth2SecurityScheme` | Dùng **OAuth 2.0** (đăng nhập chuẩn) | `flows={...}` (authorization code, client credentials...) |
| `OpenIdConnectSecurityScheme` | Dùng **OpenID Connect** (xác thực qua IdP) | `open_id_connect_url="https://idp.example.com"` |
| `MutualTlsSecurityScheme` | Dùng **chứng chỉ TLS 2 chiều** (mTLS) | Bảo mật cao, nội bộ doanh nghiệp |

- **Ví dụ API key:**
  ```python
  security_schemes={
      "ApiKeyAuth": APIKeySecurityScheme(
          description="Dùng API key trong header X-API-Key",
          location="header",
          name="X-API-Key",
      )
  }
  ```

---

#### 🟢 `security_requirements` — "Tôi cần bạn xác thực bằng cách nào"

Sau khi định nghĩa các scheme ở trên, field này nói rõ: **gọi tôi cần dùng scheme nào, và cần scope (quyền) gì**.

- **Ví dụ:** "Gọi tôi phải dùng `ApiKeyAuth`":
  ```python
  security_requirements=[
      SecurityRequirement(schemes={"ApiKeyAuth": StringList(list=[])})
  ]
  ```

> 📌 **Khi nào cần quan tâm:** Khi agent của bạn có dữ liệu nhạy cảm (API trả phí, dữ liệu cá nhân...). Khi chỉ học/agent nội bộ, có thể để trống.

---

### Nhóm F — Chữ ký (signatures)

---

#### 🟢 `signatures` — Chữ ký số JWS để xác minh "danh thiếp thật"

- **Dùng để làm gì:** Chống **giả mạo Agent Card**. Kẻ xấu có thể sửa `url` trong card để chặn/bẻ dòng gọi đi chỗ khác. Chữ ký số giúp client xác minh card **thật sự do đúng nhà cung cấp ký**.
- **Khi nào dùng:** Môi trường **bảo mật cao** (tài chính, y tế...). Học tập/agent nội bộ có thể bỏ qua.
- **Ví dụ:** `AgentCardSignature(protected="...base64url header...", signature="...base64url chữ ký...", header={...})`

---

## 4. Bảng quyết định nhanh: "Khi nào cần config nào?"

| Tình huống của bạn | Config cần quan tâm |
|---|---|
| Mới bắt đầu, agent chat đơn giản | `name`, `description`, `version`, `capabilities`, `supported_interfaces`, `skills` |
| Agent chạy lâu, muốn client thấy tiến trình | `capabilities.streaming = True` |
| Agent cực kỳ lâu, client ngắt kết nối | `capabilities.push_notifications = True` |
| Nhiều agent dùng chung một server/URL | `supported_interfaces[].tenant` |
| Có dữ liệu nhạy cảm | `capabilities.extended_agent_card = True` + `security_schemes` + `security_requirements` |
| Muốn agent khác dễ "bắt chước" cách hỏi | `skills[].examples` đầy đủ |
| Chống giả mạo card | `signatures` |
| Xử lý ảnh/audio/file | `default_input_modes` / `default_output_modes` thêm loại media |

---

## 5. Ví dụ trực quan theo mức độ phức tạp

### 📘 Ví dụ 1 — Agent học tập đơn giản (giống notebook của bạn)

```python
from a2a.types import AgentCard, AgentCapabilities, AgentInterface, AgentSkill

agent_card = AgentCard(
    name="Currency Agent",
    description="Chuyên gia tài chính: chuyển đổi tiền tệ giữa các đơn vị.",
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
            url="http://127.0.0.1:41253/a2a/jsonrpc",
        )
    ],
)
```

**Tại sao ví dụ này "đủ dùng"?** Vì tất cả trường 🔴 bắt buộc đều có, agent chat bằng text, giao tiếp qua JSON-RPC, một kỹ năng rõ ràng. Đúng "mức tối thiểu mà vẫn hợp lệ".

---

### 📗 Ví dụ 2 — Agent "đa kênh" (streaming + nhiều giao thức + nhiều kỹ năng)

Giả sử bạn có một **Assistant Agent** vừa chat vừa tạo ảnh, hỗ trợ streaming:

```python
from a2a.types import (
    AgentCard, AgentCapabilities, AgentInterface, AgentProvider, AgentSkill,
)

agent_card = AgentCard(
    name="Creative Assistant",
    description="Hỗ trợ trò chuyện và tạo hình ảnh.",
    provider=AgentProvider(organization="My Studio", url="https://mystudio.com"),
    version="2.1.0",
    capabilities=AgentCapabilities(
        streaming=True,          # đẩy kết quả từng phần -> client thấy tiến trình
        push_notifications=False,
        extended_agent_card=False,
    ),
    default_input_modes=["text"],                     # nhận text
    default_output_modes=["text", "image/png"],       # trả text hoặc ảnh PNG
    skills=[
        AgentSkill(id="chat", name="Chat", description="Trò chuyện thông thường.",
                   tags=["chat"], examples=["Xin chào"]),
        AgentSkill(id="image", name="Image generation", description="Tạo ảnh từ mô tả.",
                   tags=["image", "draw"], examples=["Vẽ một con mèo hoạt hình"],
                   output_modes=["image/png"]),       # ghi đè: kỹ năng này trả ảnh
    ],
    supported_interfaces=[
        AgentInterface(protocol_binding="JSONRPC", protocol_version="1.0",
                       url="https://assistant.example.com/a2a/jsonrpc"),
        AgentInterface(protocol_binding="GRPC", protocol_version="1.0",
                       url="assistant.example.com:443"),
    ],
)
```

**Điểm mới học được:**
- `output_modes=["image/png"]` → agent trả ảnh.
- `AgentSkill.output_modes` **ghi đè** mặc định cho riêng kỹ năng "image".
- **2 interface** → client có thể chọn JSON-RPC hoặc gRPC (ưu tiên cái đầu tiên).

---

### 📕 Ví dụ 3 — Agent bảo mật (yêu cầu API key, danh thiếp mở rộng)

```python
from a2a.types import (
    AgentCard, AgentCapabilities, AgentInterface, AgentSkill,
    APIKeySecurityScheme, SecurityRequirement, StringList,
)

agent_card = AgentCard(
    name="Internal Analytics Agent",
    description="Truy vấn số liệu nội bộ (chỉ cho nội bộ công ty).",
    version="1.0.0",
    capabilities=AgentCapabilities(
        streaming=True,
        push_notifications=False,
        extended_agent_card=True,   # có danh thiếp mở rộng cho người đã xác thực
    ),
    default_input_modes=["text"],
    default_output_modes=["text", "task-status"],
    skills=[
        AgentSkill(id="analytics", name="Analytics", description="Trả lời câu hỏi về dữ liệu.",
                   tags=["analytics"], examples=["Doanh thu tuần này?"],
                   input_modes=["text"], output_modes=["text", "task-status"]),
    ],
    supported_interfaces=[
        AgentInterface(protocol_binding="JSONRPC", protocol_version="1.0",
                       url="https://analytics.example.com/a2a/jsonrpc"),
    ],
    security_schemes={
        "ApiKeyAuth": APIKeySecurityScheme(
            description="Gửi API key trong header X-API-Key",
            location="header",
            name="X-API-Key",
        ),
    },
    security_requirements=[
        SecurityRequirement(schemes={"ApiKeyAuth": StringList(list=[])}),
    ],
)
```

**Điểm mới học được:**
- `security_schemes` khai báo cách xác thực; `security_requirements` nói rõ "bắt buộc phải dùng".
- `extended_agent_card=True` → client nào chưa xác thực chỉ thấy bản "thu gọn"; xác thực rồi mới thấy chi tiết đầy đủ.

---

## 6. Mẹo & lỗi thường gặp

1. **Quên `supported_interfaces` → client không biết gọi vào đâu.** Đây là lỗi phổ biến nhất khi "danh thiếp" có tên mà không có số điện thoại. 📞
2. **Khai `streaming=False` nhưng server vẫn gửi streaming** → client nhận lỗi theo đặc tả. Hãy khai đúng với thực tế.
3. **Mô tả/kỹ năng mơ hồ** → LLM/orchestrator chọn nhầm agent. Viết `description` + `examples` thật cụ thể.
4. **Thứ tự `supported_interfaces`** = thứ tự ưu tiên. Đặt giao thức bạn muốn client dùng nhất lên đầu.
5. **Tăng `version` khi đổi khả năng** để client không dùng card cũ (cache).
6. **Tên trường:** nhớ 2 cách viết — camelCase (JSON) / snake_case (Python SDK).

---

## 7. Tham khảo trong repo

- Đặc tả chính thức: `refs/A2A/docs/specification.md` → mục **4.4.1 AgentCard** và **5. Agent Discovery (the Agent Card)**.
- Khái niệm: `refs/A2A/docs/topics/key-concepts.md` → mục **Agent Cards**.
- Khám phá agent: `refs/A2A/docs/topics/agent-discovery.md`.
- Định nghĩa proto đầy đủ (comment gốc): `refs/A2A/specification/a2a.proto` → `message AgentCard` (dòng ~362).
- Code thực tế: `my_a2a_system/weather_agent.py`, `news_agent.py`, `currency_agent.py`, `orchestrator_agent.py` — mỗi file có một `AgentCard(...)`.
