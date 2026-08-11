"""Các hàm tiện ích dùng chung cho hệ thống A2A mini trong bài học."""
import asyncio
import os
import time
import uuid

import httpx

from a2a.client import ClientCallContext, ClientConfig, create_client
from a2a.helpers import get_artifact_text, get_message_text
from a2a.types import Message, Part, Role, SendMessageRequest, TaskState

# Có .env chứa API key không? Có thì nạp vào.
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

import asyncio
from langchain_deepseek import ChatDeepSeek
from langchain_core.messages import HumanMessage



def get_model():
    # """Trả về chuỗi model nếu có đủ API key, ngược lại None (chế độ MOCK)."""
    # provider = DEFAULT_MODEL.split(":")[0]
    # key_names = PROVIDER_KEYS.get(provider, ())
    # if any(os.environ.get(k) for k in key_names):
    #     return DEFAULT_MODEL
    # return None
    llm = ChatDeepSeek(
        model="deepseek-chat",
        temperature=0.7,
        max_tokens=1024
    )
    return llm


async def run_deep_agent(agent, query, thread_id="thread-1"):
    """Chạy agent với câu hỏi, trả về câu trả lời dạng text.

    - DeepAgent (compiled graph): input phải là dict state {"messages": [...]}
      + config thread; result là state dict -> lấy "messages"[-1].content
    - ChatModel thường (như ChatDeepSeek): input là list message; result là
      AIMessage -> lấy .content trực tiếp
    """
    if hasattr(agent, "nodes"):  # DeepAgent (compiled LangGraph)
        result = await agent.ainvoke(
            {"messages": [HumanMessage(content=query)]},
            config={"configurable": {"thread_id": thread_id}},
        )
        content = result["messages"][-1].content
    else:  # ChatModel thường
        result = await agent.ainvoke([HumanMessage(content=query)])
        content = result.content

    # Nội dung có thể là chuỗi đơn giản, hoặc danh sách các "block" (text, image...)
    if isinstance(content, list):
        texts = []
        for block in content:
            if isinstance(block, dict) and block.get("type") == "text":
                texts.append(block.get("text", ""))
        return "\n".join(t for t in texts if t)
    return str(content)



# Tiền tố đánh dấu "worker đang cần người dùng xác nhận (HITL)".
# Khi call_agent() không được truyền ask_user, nó trả về chuỗi dạng:
#   "__HITL__::<task_id>|<context_id>|<câu hỏi>"
# để bên gọi (ví dụ orchestrator) tự quyết định cách hỏi người dùng.
HITL_PREFIX = "__HITL__::"


async def call_agent(base_url, user_text, verbose=True, ask_user=None,
                     task_id=None, context_id=None):
    """Gọi một A2A server và trả về toàn bộ nội dung trong artifact.

    Đây chính là "khách hàng" (A2A Client):
      1. Resolve Agent Card từ URL (đọc "danh thiếp")
      2. Gửi SendMessage (truyền task_id/context_id -> gửi TIẾP vào task cũ)
      3. Lắng nghe dòng sự kiện: status update + artifact update
      4. Nếu server chuyển sang input-required (HITL):
         - Có ask_user: gọi ask_user(câu_hỏi) lấy câu trả lời, gửi lại cho
           CÙNG task, tiếp tục tới khi hoàn thành.
         - Không có ask_user: trả về "__HITL__::<task_id>|<context_id>|<câu_hỏi>"
           để bên gọi (orchestrator) tự xử lý việc hỏi người dùng.
    """
    artifacts = []
    current_text = user_text
    cur_task_id = task_id
    cur_context_id = context_id
    async with httpx.AsyncClient() as httpx_client:
        config = ClientConfig(httpx_client=httpx_client)
        client = await create_client(base_url, client_config=config)
        try:
            while True:
                message = Message(
                    role=Role.ROLE_USER,
                    message_id=str(uuid.uuid4()),
                    parts=[Part(text=current_text)],
                    task_id=cur_task_id,
                    context_id=cur_context_id,
                )
                request = SendMessageRequest(message=message)

                question = None  # nếu server cần input (HITL), lưu câu hỏi ở đây
                async for event in client.send_message(
                    request, context=ClientCallContext(timeout=300.0)
                ):
                    if event.HasField("task"):
                        cur_task_id = event.task.id
                        cur_context_id = event.task.context_id
                    elif event.HasField("status_update"):
                        su = event.status_update
                        if su.task_id:
                            cur_task_id = su.task_id
                        if su.context_id:
                            cur_context_id = su.context_id
                        state = TaskState.Name(su.status.state)
                        extra = ""
                        if su.status.HasField("message"):
                            extra = get_message_text(
                                su.status.message, delimiter=" "
                            )
                        if verbose:
                            print(f"      [status] {state} {extra}".rstrip())
                        if state == "TASK_STATE_INPUT_REQUIRED":
                            question = extra
                    elif event.HasField("artifact_update"):
                        text = get_artifact_text(
                            event.artifact_update.artifact, delimiter="\n"
                        )
                        if text.strip():
                            artifacts.append(text)

                if question is None:
                    break  # task đã kết thúc -> thoát vòng lặp

                # ---- Server đang cần người dùng (HITL) ----
                if ask_user is None:
                    # Không có cách hỏi người dùng -> trả "dấu hiệu HITL"
                    # kèm id của task để bên gọi tiếp tục sau khi có câu trả lời.
                    return (
                        f"{HITL_PREFIX}{cur_task_id}|{cur_context_id}|{question}"
                    )
                # Hỏi người dùng rồi gửi câu trả lời lại cho CÙNG task.
                # ask_user có thể là hàm thường (trả về str) hoặc async (coroutine).
                reply = ask_user(question)
                if asyncio.iscoroutine(reply):
                    reply = await reply
                current_text = reply
        finally:
            await client.close()
    return "\n".join(artifacts)


async def wait_for_server(base_url, timeout=90):
    """Chờ cho tới khi server phục vụ được Agent Card (tức server đã sẵn sàng)."""
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
    return False