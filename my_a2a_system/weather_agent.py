"""Weather Agent - một A2A Server với "bộ não" là DeepAgent (hoặc mock)."""
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
    Task,
    TaskState,
    TaskStatus,
)

from a2a_common import get_model, run_deep_agent

logger = logging.getLogger(__name__)


def build_deep_agent():
    """Tạo DeepAgent làm "bộ não" thật. Chưa có API key -> None (dùng mock)."""
    model = get_model()
    if model is None:
        return None

    from deepagents import create_deep_agent
    from langchain.tools import tool

    @tool
    def get_weather(city: str) -> str:
        """Trả về thời tiết hiện tại của một thành phố."""
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
    """Bộ não xử lý mỗi yêu cầu. Framework gọi execute() khi có message mới."""

    def __init__(self, agent):
        self.agent = agent

    async def execute(self, context: RequestContext, event_queue: EventQueue):
        # 1) Đọc câu hỏi người dùng
        user_input = context.get_user_input()
        task_id = context.task_id
        context_id = context.context_id

        # 2) BẮT BUỘC: gửi Task ban đầu (submitted) TRƯỚC các status update
        await event_queue.enqueue_event(
            Task(
                id=task_id,
                context_id=context_id,
                status=TaskStatus(state=TaskState.TASK_STATE_SUBMITTED),
                history=[context.message],
            )
        )

        # 3) "Phát thanh viên" báo trạng thái cho client
        updater = TaskUpdater(event_queue, task_id, context_id)
        await updater.start_work(
            message=updater.new_agent_message(
                parts=[Part(text="Đang kiểm tra thời tiết...")]
            )
        )

        # 4) Suy nghĩ: DeepAgent thật HOẶC mock brain
        answer = await run_deep_agent(self.agent, user_input, thread_id=task_id)

        # 5) Giao kết quả (artifact) và báo hoàn thành
        await updater.add_artifact(
            parts=[Part(text=answer)], name="response", last_chunk=True
        )
        await updater.complete()

    def mock_brain(self, query: str) -> str:
        """Bộ não giả - không cần LLM, chỉ để học phần giao tiếp A2A."""
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
    """Lắp ráp server: Agent Card + Request Handler + routes."""
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
    main()
