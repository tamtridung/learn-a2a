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



async def call_agent(base_url, user_text, verbose=True):
    """Gọi một A2A server và trả về toàn bộ nội dung trong artifact.

    Đây chính là "khách hàng" (A2A Client):
      1. Resolve Agent Card từ URL (đọc "danh thiếp")
      2. Tạo client
      3. Gửi SendMessage
      4. Lắng nghe dòng sự kiện: status update + artifact update
    """
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

        # Duyệt qua từng sự kiện server gửi về (stream).
        # Truyền ClientCallContext(timeout=...) để tránh ReadTimeout
        # (mặc định httpx 5s) khi server chạy LLM thật hoặc điều phối nhiều worker.
        async for event in client.send_message(
            request, context=ClientCallContext(timeout=300.0)
        ):
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
                    event.artifact_update.artifact, delimiter="\n"
                )
                if text.strip():
                    artifacts.append(text)

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