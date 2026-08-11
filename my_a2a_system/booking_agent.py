"""Booking Agent - một A2A Server minh hoạ HUMAN-IN-THE-LOOP (HITL), dùng LLM thật.

Booking Agent có "bộ não" là DeepAgent THẬT (DeepSeek) để:
  - Hiểu yêu cầu đặt vé bằng ngôn ngữ tự nhiên.
  - Gọi tool prepare_booking để lấy giá vé.
  - SOẠN câu hỏi xác nhận cho người dùng.

Câu trả lời của người dùng cũng được hiểu BẰNG LLM (KHÔNG hardcode từ khoá):
  - 'ok', 'okie', 'chốt', 'chắc chắn rồi', 'yes please'... -> ĐỒNG Ý -> đặt vé.
  - Các câu trả lời khác -> agent HỎI LẠI (vòng lặp) cho tới khi người dùng xác nhận thật sự.
  Nếu chưa có API key, dùng fallback nhận diện từ khoá (mock).

VÒNG LẶP HITL (lặp lại nhiều lần, không chỉ 1 lần):
  1. Lần gọi 1: chạy DeepAgent để soạn câu hỏi, publish `requires_input(...)`
     rồi TRẢ VỀ (nhường quyền cho người dùng).
  2. Lần gọi 2+ (resume, cùng task_id): đọc câu trả lời.
     - Xác nhận -> complete() (đặt vé).
     - Chưa xác nhận -> chạy DeepAgent (với checkpointer nhớ cả hội thoại) để
       soạn câu hỏi TIẾP THEO, gọi requires_input(...) và TRẢ VỀ -> LẶP LẠI.
"""
import argparse
import logging

import uvicorn
from fastapi import FastAPI
from langchain_core.messages import HumanMessage

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
from langgraph.checkpoint.memory import InMemorySaver
from a2a_common import get_model, run_deep_agent

logger = logging.getLogger(__name__)

# Giá vé giả lập (VND) cho từng cặp chặng bay
FLIGHT_PRICES = {
    ("hanoi", "danang"): 1_500_000,
    ("danang", "hanoi"): 1_500_000,
    ("hanoi", "hcmc"): 2_200_000,
    ("hcmc", "hanoi"): 2_200_000,
}

# Tên gọi tắt của các thành phố (để chuẩn hoá từ ngôn ngữ tự nhiên -> key nội bộ)
CITY_ALIASES = {
    "hanoi": ["hà nội", "hanoi", "ha noi", "hn"],
    "danang": ["đà nẵng", "danang", "da nang", "dn"],
    "hcmc": ["hồ chí minh", "hcmc", "sài gòn", "saigon", "hcm"],
}


def normalize_city(name: str) -> str:
    """Chuẩn hoá tên thành phố do LLM truyền vào -> key nội bộ (hanoi/danang/hcmc)."""
    n = name.strip().lower()
    for key, aliases in CITY_ALIASES.items():
        if any(a in n for a in aliases):
            return key
    return n  # không nhận diện được -> giữ nguyên (sẽ dùng giá fallback)


def build_deep_agent(model=None):
    """Tạo DeepAgent làm "bộ não" thật. Chưa có API key -> None (dùng mock)."""
    if model is None:
        model = get_model()
    if model is None:
        return None

    from deepagents import create_deep_agent
    from langchain.tools import tool

    @tool
    def prepare_booking(from_city: str, to_city: str) -> str:
        """Chuẩn bị vé: trả về giá vé (VND) cho một chặng bay."""
        price = FLIGHT_PRICES.get(
            (normalize_city(from_city), normalize_city(to_city)), 1_200_000
        )
        return f"Giá vé {from_city} → {to_city} là {price:,} VND."

    # checkpointer=InMemorySaver() -> agent CÓ TRÍ NHỚ theo thread_id (= task_id),
    # nhờ đó vòng lặp HITL hỏi lại vẫn nhớ yêu cầu gốc và các lượt trước.
    return create_deep_agent(
        name="booking_agent",
        model=model,
        tools=[prepare_booking],
        system_prompt=(
            "Bạn là chuyên gia đặt vé máy bay.\n"
            "Khi nhận yêu cầu đặt vé:\n"
            "1. Trích 'nơi đi' và 'nơi đến' từ yêu cầu, rồi gọi tool "
            "prepare_booking để lấy giá vé.\n"
            "2. Trả lời ĐÚNG MỘT câu hỏi xác nhận ngắn gọn, ví dụ:\n"
            "   'Bạn xác nhận đặt vé Hà Nội → Đà Nẵng giá 1,500,000 VND? (có/không)'\n"
            "KHÔNG tự ý xác nhận vé. Nếu người dùng chưa đồng ý (trả lời khác 'có'), "
            "hãy HỎI LẠI hoặc hướng dẫn theo ngữ cảnh, KHÔNG kết thúc đặt vé."
        ),
        checkpointer=InMemorySaver()
    )


def parse_booking(query: str):
    """(Chỉ dùng cho mock brain) Trích "nơi đi" và "nơi đến" từ câu hỏi."""
    q = query.lower()
    cities = {
        "hà nội": "hanoi", "hanoi": "hanoi", "ha noi": "hanoi",
        "đà nẵng": "danang", "danang": "danang", "da nang": "danang",
        "hồ chí minh": "hcmc", "hcmc": "hcmc", "sài gòn": "hcmc",
    }
    found = [name for key, name in cities.items() if key in q]
    if len(found) >= 2:
        return found[0], found[1]
    if len(found) == 1:
        return found[0], "danang"
    return None, None


class BookingExecutor(AgentExecutor):
    """Bộ não xử lý. `pending` nhớ các task đang chờ người dùng xác nhận."""

    def __init__(self, agent, llm=None):
        self.agent = agent   # DeepAgent: soạn câu hỏi xác nhận (có checkpointer -> nhớ hội thoại)
        self.llm = llm       # LLM thường: hiểu câu trả lời của người dùng
        self.pending = {}    # task_id -> True (đang chờ xác nhận)

    async def execute(self, context: RequestContext, event_queue: EventQueue):
        task_id = context.task_id
        context_id = context.context_id
        user_input = context.get_user_input()
        updater = TaskUpdater(event_queue, task_id, context_id)

        # ============ LẦN GỌI ĐẦU: soạn câu hỏi xác nhận ============
        if task_id not in self.pending:
            # BẮT BUỘC: gửi Task (submitted) TRƯỚC các status update
            await event_queue.enqueue_event(
                Task(
                    id=task_id,
                    context_id=context_id,
                    status=TaskStatus(state=TaskState.TASK_STATE_SUBMITTED),
                    history=[context.message],
                )
            )

            await updater.start_work(
                message=updater.new_agent_message(
                    parts=[Part(text="Đang lên vé, vui lòng chờ...")]
                )
            )

            # Suy nghĩ: DeepAgent thật (LLM) HOẶC mock brain nếu không có API key
            question = await run_deep_agent(
                self.agent, user_input, thread_id=task_id
            )

            # Phòng thủ: nếu LLM trả về trống/quá dài -> dùng câu hỏi mặc định
            if not question.strip() or len(question) > 500:
                question = (
                    "Bạn xác nhận đặt vé máy bay? (trả lời 'có' hoặc 'không')"
                )

            self.pending[task_id] = True
            # HITL: chuyển task sang input-required và TRẢ VỀ (nhường quyền).
            # KHÔNG gọi complete() - chờ người dùng trả lời ở lần gọi sau.
            await updater.requires_input(
                message=updater.new_agent_message(parts=[Part(text=question)])
            )
            return

        # ============ LẦN GỌI THỨ 2+: vòng lặp xác nhận ============
        self.pending.pop(task_id)

        # Hiểu ý người dùng BẰNG LLM (flexible: 'okie', 'chốt'... đều bắt được).
        confirmed = await self._is_confirmed(user_input)

        if confirmed:
            await updater.start_work(
                message=updater.new_agent_message(
                    parts=[Part(text="Đang xác nhận đặt vé...")]
                )
            )
            await updater.add_artifact(
                parts=[Part(
                    text=(
                        "✅ ĐẶT VÉ THÀNH CÔNG!\n"
                        f"- Mã vé: BK-{task_id[:8].upper()}\n"
                        "Cảm ơn bạn đã sử dụng dịch vụ đặt vé!"
                    )
                )],
                name="response",
                last_chunk=True,
            )
            await updater.complete()
        else:
            # CHƯA xác nhận -> HỎI LẠI (vòng lặp HITL), KHÔNG complete().
            # Nhờ checkpointer (InMemorySaver), agent nhớ cả cuộc hội thoại theo
            # thread_id=task_id nên câu hỏi tiếp theo luôn đúng ngữ cảnh.
            if self.agent is not None:
                reply = await run_deep_agent(
                    self.agent, user_input, thread_id=task_id
                )
            else:
                reply = (
                    "Bạn vẫn muốn đặt vé chứ? Nếu có, hãy trả lời 'có' để tôi đặt. "
                    "Nếu muốn đổi chặng, hãy nói rõ nơi đi và nơi đến nhé!"
                )
            if not reply.strip():
                reply = (
                    "Bạn vẫn muốn đặt vé chứ? Nếu có, hãy trả lời 'có' để tôi đặt nhé!"
                )

            self.pending[task_id] = True  # vẫn đang chờ xác nhận (vòng lặp)
            await updater.requires_input(
                message=updater.new_agent_message(parts=[Part(text=reply)])
            )
            return

    async def _is_confirmed(self, answer: str) -> bool:
        """Hiểu câu trả lời của người dùng có phải "đồng ý" không.

        - Có LLM: hỏi LLM phân loại (hiểu theo ngữ cảnh, KHÔNG cần liệt kê từ khoá).
        - Không có LLM: fallback nhận diện từ khoá (mock).
        """
        if self.llm is not None:
            prompt = (
                "Người dùng vừa trả lời câu hỏi xác nhận đặt vé máy bay.\n"
                f"Câu trả lời của họ: '{answer}'\n"
                "Họ có ĐỒNG Ý đặt vé không?\n"
                "Chỉ trả lời đúng MỘT từ: CÓ hoặc KHÔNG."
            )
            result = await self.llm.ainvoke([HumanMessage(content=prompt)])
            return self._parse_yes_no(str(result.content))
        return self._keyword_is_confirmed(answer)

    @staticmethod
    def _parse_yes_no(reply: str) -> bool:
        """Đọc 'bản án' CÓ/KHÔNG do LLM trả về."""
        upper = reply.strip().upper()
        if "KHÔNG" in upper or upper in ("NO", "N"):
            return False
        if "CÓ" in upper or upper in ("OK", "OKE", "OKIE", "YES", "YEAH", "YEP"):
            return True
        return False  # không rõ -> mặc định KHÔNG xác nhận (an toàn, không tính phí)

    @staticmethod
    def _keyword_is_confirmed(answer: str) -> bool:
        """Fallback (không có LLM): nhận diện bằng từ khoá."""
        a = answer.strip().lower()
        yes_words = [
            "có", "ok", "oke", "okie", "yes", "yeah", "yep",
            "đồng ý", "xác nhận", "chốt", "chuẩn", "đúng", "chắc chắn",
            "agree", "confirmed", "go ahead",
        ]
        return any(w in a for w in yes_words)


    async def cancel(self, context: RequestContext, event_queue: EventQueue):
        updater = TaskUpdater(event_queue, context.task_id, context.context_id)
        await updater.cancel()


def create_app(host: str, port: int):
    """Lắp ráp server: Agent Card + Request Handler + routes."""
    # Lấy model MỘT lần: dùng cho cả soạn câu hỏi (DeepAgent) và hiểu câu trả lời (LLM)
    llm = get_model()
    agent = build_deep_agent(llm)

    agent_card = AgentCard(
        name="Booking Agent",
        description="Chuyên gia đặt vé máy bay (LLM): luôn hỏi người dùng xác nhận trước khi đặt (HITL).",
        provider=AgentProvider(organization="A2A Course", url="http://example.com"),
        version="1.0.0",
        capabilities=AgentCapabilities(streaming=True, push_notifications=False),
        default_input_modes=["text"],
        default_output_modes=["text", "task-status"],
        skills=[
            AgentSkill(
                id="booking",
                name="Flight booking with confirmation",
                description="Đặt vé máy bay; yêu cầu người dùng xác nhận (input-required).",
                tags=["booking", "hitl"],
                examples=["Đặt vé Hà Nội đi Đà Nẵng"],
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
        agent_executor=BookingExecutor(agent, llm),
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
    parser.add_argument("--port", type=int, default=41254)
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO)
    uvicorn.run(create_app(args.host, args.port), host=args.host, port=args.port)


if __name__ == "__main__":
    main()
