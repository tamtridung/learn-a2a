"""Orchestrator Agent - điều phối 3 worker agents qua giao thức A2A.

Vừa là A2A Server (nhận yêu cầu từ User) vừa là A2A Client (gọi worker).
"""
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
    """DeepAgent làm "bộ não điều phối". Chưa có API key -> None (dùng mock)."""
    model = get_model()
    if model is None:
        return None

    from deepagents import create_deep_agent
    from langchain.tools import tool

    # Mỗi tool = một "đường dây điện thoại" tới một worker qua A2A
    @tool
    async def ask_weather(query: str) -> str:
        """Gửi câu hỏi về thời tiết cho Weather Agent."""
        return await call_agent(WEATHER_URL, query, verbose=False)

    @tool
    async def ask_news(query: str) -> str:
        """Gửi câu hỏi về tin tức cho News Agent."""
        return await call_agent(NEWS_URL, query, verbose=False)

    @tool
    async def ask_currency(query: str) -> str:
        """Gửi câu hỏi về chuyển đổi tiền tệ cho Currency Agent."""
        return await call_agent(CURRENCY_URL, query, verbose=False)

    return create_deep_agent(
        name="orchestrator",
        model=model,
        tools=[ask_weather, ask_news, ask_currency],
        system_prompt=(
            "Bạn là đội trưởng điều phối. Quy tắc:\n"
            "- Hỏi về thời tiết -> gọi ask_weather\n"
            "- Hỏi về tin tức -> gọi ask_news\n"
            "- Hỏi về tiền tệ/đổi tiền -> gọi ask_currency\n"
            "- Yêu cầu phức tạp -> gọi NHIỀU tool và tổng hợp.\n"
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

        answer = await run_deep_agent(self.agent, user_input, thread_id=task_id)
        await updater.add_artifact(
            parts=[Part(text=answer)], name="response", last_chunk=True
        )
        await updater.complete()

    # async def mock_orchestrate(self, query: str) -> str:
    #     """Mock brain: vẫn THỰC SỰ gọi các worker qua A2A (chỉ thiếu phần "suy luận")."""
    #     q = query.lower()
    #     tasks = []
    #     if any(w in q for w in ["thời tiết", "weather", "nhiệt độ", "trời"]):
    #         tasks.append(("Weather", WEATHER_URL))
    #     if any(w in q for w in ["tin tức", "news", "bản tin"]):
    #         tasks.append(("News", NEWS_URL))
    #     if any(w in q for w in ["tiền", "đổi", "usd", "vnd", "eur", "gbp", "jpy", "giá"]):
    #         tasks.append(("Currency", CURRENCY_URL))

    #     if not tasks:
    #         return (
    #             "Tôi là orchestrator. Tôi có thể giúp bạn về: thời tiết, tin tức, "
    #             "chuyển đổi tiền tệ. Hãy thử hỏi: 'Thời tiết Hà Nội thế nào?'"
    #         )

    #     results = []
    #     for name, url in tasks:
    #         result = await call_agent(url, query, verbose=False)
    #         results.append(f"[{name}]\n{result}")
    #     return "\n\n".join(results)

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
    main()
