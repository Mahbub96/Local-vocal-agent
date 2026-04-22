from __future__ import annotations

import json
import re

from langchain.agents import AgentExecutor, create_tool_calling_agent
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder

from app.agents.tools import build_memory_search_tool, build_web_search_tool
from app.core.settings import get_settings
from app.integrations.ollama.llm import OllamaChatModel
from app.integrations.search.duckduckgo import DuckDuckGoSearchClient
from app.memory.long_term.retriever import LongTermMemoryRetriever
from app.services.memory_service import MemoryContext


settings = get_settings()

REALTIME_PATTERN = re.compile(
    r"\b(weather|news|latest|today|current|now|stock|price|forecast|headline|recent)\b",
    re.IGNORECASE,
)


class AssistantAgent:
    """LangChain-based assistant orchestration with tool gating."""

    def __init__(
        self,
        *,
        retriever: LongTermMemoryRetriever,
        search_client: DuckDuckGoSearchClient | None = None,
        llm: OllamaChatModel | None = None,
    ) -> None:
        self.retriever = retriever
        self.search_client = search_client or DuckDuckGoSearchClient()
        self.llm = (llm or OllamaChatModel()).client

    def needs_internet_search(self, query: str) -> bool:
        return bool(REALTIME_PATTERN.search(query))

    async def run(self, *, query: str, memory_context: MemoryContext) -> dict[str, object]:
        use_search = self.needs_internet_search(query)
        tools = [build_web_search_tool(self.search_client)] if use_search else [
            build_memory_search_tool(self.retriever)
        ]

        system_prompt = (
            "You are a local AI assistant. "
            "Use local memory for historical context. "
            "Use internet search only for real-time or externally changing facts. "
            "Keep answers grounded, concise, and practical."
        )
        prompt = ChatPromptTemplate.from_messages(
            [
                ("system", system_prompt),
                ("system", "Recent conversation:\n{short_term_context}"),
                ("system", "Retrieved long-term memory:\n{long_term_context}"),
                ("human", "{input}"),
                MessagesPlaceholder(variable_name="agent_scratchpad"),
            ]
        )
        agent = create_tool_calling_agent(self.llm, tools, prompt)
        executor = AgentExecutor(agent=agent, tools=tools, verbose=False)

        long_term_context = "\n".join(
            f"[{msg.role}] {msg.content}" for msg in memory_context.long_term_messages
        ) or "No semantically relevant memory retrieved."
        short_term_context = "\n".join(
            f"[{msg['role']}] {msg['content']}" for msg in memory_context.short_term_messages
        ) or "No recent conversation context."

        result = await executor.ainvoke(
            {
                "input": query,
                "short_term_context": short_term_context,
                "long_term_context": long_term_context,
            }
        )
        return {
            "response": result["output"],
            "used_internet": use_search,
            "used_memory": not use_search,
            "tool_result": json.dumps(result.get("intermediate_steps", []), default=str),
        }
