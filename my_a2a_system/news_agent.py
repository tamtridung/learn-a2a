"""News Agent - trả lời tin tức theo chủ đề."""
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
    def get_news(topic: str) -> str:
        """Trả về các dòng tít tin tức nổi bật về một chủ đề."""
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
                return "\n".join(f"- {h}" for h in v)
        return f"- Tin nóng về {topic}\n- Phân tích chuyên sâu về {topic}"

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
                parts=[Part(text="Đang tìm tin tức...")]
            )
        )

        answer = await run_deep_agent(self.agent, user_input, thread_id=task_id)
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
                    f"[MOCK news] Tin nổi bật về {label}:\n"
                    f"- Tiêu đề số 1 về {label}\n"
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
    main()
