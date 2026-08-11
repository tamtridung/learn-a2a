"""Currency Agent - chuyển đổi tiền tệ."""
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
    Task,
    TaskState,
    TaskStatus,
)

from a2a_common import get_model, run_deep_agent

logger = logging.getLogger(__name__)

# Tỷ giá giả lập (đơn vị: 1 ngoại tệ = X VND)
RATES = {"USD": 24500, "EUR": 26500, "GBP": 31000, "JPY": 165, "VND": 1}


def build_deep_agent():
    """Tạo DeepAgent làm "bộ não" thật. Chưa có API key -> None (dùng mock)."""
    model = get_model()
    if model is None:
        return None

    from deepagents import create_deep_agent
    from langchain.tools import tool

    @tool
    def convert_currency(amount: float, from_ccy: str, to_ccy: str) -> str:
        """Chuyển một số tiền từ đơn vị tiền tệ này sang đơn vị khác."""
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
                parts=[Part(text="Đang tra tỷ giá...")]
            )
        )

        answer = await run_deep_agent(self.agent, user_input, thread_id=task_id)

        await updater.add_artifact(
            parts=[Part(text=answer)], name="response", last_chunk=True
        )
        await updater.complete()

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
    main()
