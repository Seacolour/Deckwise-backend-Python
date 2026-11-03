"""Deterministic context loading and model/tool steps for one Agent turn."""

from collections.abc import Callable, Sequence
from typing import Literal

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langchain_core.tools import BaseTool
from langgraph.graph import END
from langgraph.prebuilt import ToolNode

from app.agent.state import AgentState
from app.services import document_service

MAX_TOOL_ROUNDS = 6


def make_context_node(user_id: int, project_id: int) -> Callable:
    def load_context(state: AgentState) -> dict:
        document_id = state.get("active_document_id")
        referenced = state.get("referenced_document_ids") or []
        attached_files = state.get("attached_file_keys") or []
        references_note = f" 用户另外引用了文档 ID：{referenced}。" if referenced else ""
        if attached_files:
            references_note += f" 本轮附加文件 cache_key：{attached_files}。请用 file_content_read 分段读取。"
        if document_id is None:
            return {"context_note": "当前没有选中的文档。可以先用 file_list 找到项目内文档。" + references_note}
        document = document_service.get_document(
            user_id, document_id, False, expected_project_id=project_id,
        )
        return {"context_note": (
            f"当前文档 ID={document.id}，标题={document.title}，版本={document.version}。"
            "如需正文，请调用 document_read。" + references_note
        )}

    return load_context


def make_model_node(model: BaseChatModel, tools: Sequence[BaseTool], mode: str,
                    image_urls: Sequence[str] = ()) -> Callable:
    bound_model = model.bind_tools(tools)

    async def call_model(state: AgentState) -> dict:
        instruction = (
            "你是项目内的中文文档助手。所有面向用户的说明和最终回复都使用中文。"
            "只能使用提供的工具访问当前项目，"
            "不得声称已完成未实际执行的写入。回答应简洁。"
        )
        if mode == "AGENT":
            instruction += (
                "用户要求新建文档时使用 document_create；如需根据附件创作，先用 file_content_read 阅读资料。"
                "局部编辑时用 document_locate 找到精确原文和行号，再用 document_diff 修改工作副本，"
                "最后调用 document_save，传入版本但省略 draft_content。"
                "也可先用 document_read 获取完整草稿，再用 document_save 提交完整的新草稿。"
                "遇到版本冲突时重新读取后再决定是否重试，不能盲目覆盖。"
            )
        else:
            instruction += "当前是问答模式，只读取资料并回答，不修改文档。"
        instruction += "对于用户附加的文件，应调用 file_content_read 按需读取文本分片，不要假设文件内容已进入上下文。"
        instruction += "对于 JSON 文件，可先用 json_structure_read 查看结构，再按返回的 JSON Pointer 用 json_subtree_read 读取局部内容。"
        if image_urls:
            instruction += "本轮附加图片已作为视觉输入提供，请根据图片实际内容回答，不要仅凭文件名推测。"
        instruction += "\n" + state.get("context_note", "")
        messages = list(state["messages"])
        if image_urls:
            for index in range(len(messages) - 1, -1, -1):
                if isinstance(messages[index], HumanMessage):
                    original = messages[index]
                    messages[index] = HumanMessage(content=[
                        {"type": "text", "text": str(original.content)},
                        *({"type": "image_url", "image_url": {"url": url}} for url in image_urls),
                    ])
                    break
        response = await bound_model.ainvoke([SystemMessage(content=instruction), *messages])
        return {"messages": [response]}

    return call_model


def make_tool_node(tools: Sequence[BaseTool]) -> Callable:
    tool_node = ToolNode(tools, handle_tool_errors=lambda _error: '{"success":false,"error":"工具暂时不可用"}')

    async def run_tools(state: AgentState) -> dict:
        result = await tool_node.ainvoke(state)
        return {"messages": result["messages"], "tool_rounds": state.get("tool_rounds", 0) + 1}

    return run_tools


def route_after_model(state: AgentState) -> Literal["tools", "limit", "__end__"]:
    last = state["messages"][-1]
    if not isinstance(last, AIMessage) or not last.tool_calls:
        return END
    return "tools" if state.get("tool_rounds", 0) < MAX_TOOL_ROUNDS else "limit"


def limit_notice(_state: AgentState) -> dict:
    return {"messages": [AIMessage(content="这轮已达到工具调用上限。请确认当前文档状态后继续提问。")]}
