"""
Agent Brain — the autonomous reasoning engine (LangGraph V2).

Replaces the linear ReAct loop with a LangGraph state machine for robust, branchable reasoning.
Uses the local Claude proxy at localhost:8082 with Bearer auth.
Handles thinking models that return thinking + text content blocks.
"""

import json
import asyncio
import httpx
import structlog
from typing import AsyncGenerator, Any, TypedDict, Annotated

from langgraph.graph import StateGraph, END
from config import Settings
from tools.registry import ToolRegistry
from memory.manager import MemoryManager
from core.events import EventBus, Event, EventType
from agent.schemas import ConversationContext, AgentState, ToolCall
from agent.system_prompt import build_system_prompt
from core.self_healing import SelfHealingManager
from agent.context_compressor import compress_messages

logger = structlog.get_logger(__name__)


class GraphState(TypedDict):
    context: ConversationContext
    system_prompt: str
    queue: asyncio.Queue
    tool_calls: list[ToolCall]
    iteration: int
    user_input: str


class AgentBrain:
    """
    Autonomous agent orchestrator using LangGraph.
    """

    def __init__(
        self,
        settings: Settings,
        tool_registry: ToolRegistry,
        memory_manager: MemoryManager,
        event_bus: EventBus,
    ) -> None:
        self.settings = settings
        self.tools = tool_registry
        self.memory = memory_manager
        self.event_bus = event_bus
        self.self_healing = SelfHealingManager(event_bus)
        self._interrupt = asyncio.Event()

        self._base_url = settings.claude.base_url.rstrip("/")
        self._auth_token = settings.claude.auth_token
        self._model = settings.claude.model

        self.graph = self._build_graph()

        logger.info(
            "agent_brain_initialized",
            base_url=self._base_url,
            model=self._model,
            engine="langgraph",
        )

    def _build_graph(self):
        workflow = StateGraph(GraphState)

        workflow.add_node("reasoning", self._reasoning_node)
        workflow.add_node("tools", self._tools_node)

        workflow.set_entry_point("reasoning")
        
        workflow.add_conditional_edges(
            "reasoning",
            self._route_after_reasoning,
            {
                "tools": "tools",
                "end": END
            }
        )
        
        workflow.add_edge("tools", "reasoning")
        
        return workflow.compile()

    async def _route_after_reasoning(self, state: GraphState) -> str:
        if self._interrupt.is_set():
            return "end"
            
        max_iterations = self.settings.claude.max_agent_iterations
        if state["context"].is_background:
            max_iterations = 50
            
        if state["iteration"] >= max_iterations:
            await state["queue"].put({
                "type": "response_text",
                "text": "I've reached my maximum reasoning steps. Let me know if you'd like me to continue."
            })
            return "end"
            
        if len(state["tool_calls"]) > 0:
            return "tools"
        return "end"

    async def _reasoning_node(self, state: GraphState) -> dict:
        context = state["context"]
        queue = state["queue"]
        iteration = state["iteration"] + 1
        
        context.iteration_count = iteration
        context.state = AgentState.THINKING
        logger.info("agent_iteration", iteration=iteration)

        # Compress context
        max_context_tokens = int(self.settings.claude.max_tokens * 0.8)
        context.messages = compress_messages(context.messages, max_tokens=max_context_tokens)

        full_response_text = ""
        tool_calls: list[ToolCall] = []
        content_blocks = []

        try:
            # We must stream directly to queue
            headers = {
                "Authorization": f"Bearer {self._auth_token}",
                "Content-Type": "application/json",
                "anthropic-version": "2023-06-01",
            }

            payload: dict[str, Any] = {
                "model": self._model,
                "max_tokens": self.settings.claude.max_tokens,
                "system": state["system_prompt"],
                "messages": self._serialize_messages(context.messages),
                "stream": True,
            }

            tools_schema = self.tools.get_all_schemas()
            if tools_schema:
                payload["tools"] = tools_schema

            url = f"{self._base_url}/v1/messages"
            
            async with httpx.AsyncClient(timeout=120.0) as client:
                async with client.stream("POST", url, headers=headers, json=payload) as resp:
                    if resp.status_code != 200:
                        error_body = await resp.aread()
                        raise Exception(f"Client error {resp.status_code}: {error_body.decode(errors='ignore')}")
                    
                    current_block = None
                    async for line in resp.aiter_lines():
                        if self._interrupt.is_set():
                            break
                            
                        if not line.startswith("data: "):
                            continue
                            
                        try:
                            data = json.loads(line[6:])
                        except json.JSONDecodeError:
                            continue

                        event_type = data.get("type", "")

                        if event_type == "content_block_start":
                            block = data.get("content_block", {})
                            current_block = {
                                "type": block.get("type", "text"),
                                "text": block.get("text", ""),
                                "thinking": block.get("thinking", ""),
                            }
                            if block.get("type") == "tool_use":
                                current_block["id"] = block.get("id", "")
                                current_block["name"] = block.get("name", "")
                                current_block["input_json"] = ""

                        elif event_type == "content_block_delta":
                            delta = data.get("delta", {})
                            delta_type = delta.get("type", "")

                            if current_block:
                                if delta_type == "text_delta":
                                    text_chunk = delta.get("text", "")
                                    current_block["text"] += text_chunk
                                    full_response_text += text_chunk
                                    await queue.put({"type": "response_text", "text": text_chunk})
                                    
                                elif delta_type == "thinking_delta":
                                    think_chunk = delta.get("thinking", "")
                                    current_block["thinking"] += think_chunk
                                    await queue.put({"type": "thinking", "text": think_chunk})
                                    
                                elif delta_type == "input_json_delta":
                                    current_block["input_json"] = current_block.get("input_json", "") + delta.get("partial_json", "")

                        elif event_type == "content_block_stop":
                            if current_block:
                                if current_block["type"] == "tool_use":
                                    try:
                                        current_block["input"] = json.loads(current_block.get("input_json", "{}"))
                                    except json.JSONDecodeError:
                                        current_block["input"] = {}
                                        
                                    tc = ToolCall(
                                        id=current_block["id"],
                                        name=current_block["name"],
                                        input=current_block["input"],
                                    )
                                    tool_calls.append(tc)
                                    
                                content_blocks.append(current_block)
                                current_block = None

            context.messages.append({
                "role": "assistant",
                "content": content_blocks,
            })

            # Store memory if done
            if not tool_calls and not self._interrupt.is_set():
                await self._store_interaction(
                    user_input=state["user_input"],
                    response=full_response_text, 
                    context=context
                )

        except Exception as e:
            logger.error("claude_api_error", error=str(e), error_type=type(e).__name__)
            await self.event_bus.emit(
                Event(
                    type=EventType.ERROR, 
                    data={"context": "claude_api_call", "error": str(e)},
                    conversation_id=context.conversation_id
                )
            )
            await queue.put({
                "type": "response_text",
                "text": f"I encountered an error: {str(e)}",
            })
            
        return {"iteration": iteration, "tool_calls": tool_calls}

    async def _tools_node(self, state: GraphState) -> dict:
        context = state["context"]
        queue = state["queue"]
        tool_calls = state["tool_calls"]
        tool_results = []
        
        for tc in tool_calls:
            if self._interrupt.is_set():
                break

            await queue.put({
                "type": "tool_start",
                "tool": tc.name,
                "input": tc.input,
            })

            if self.tools.is_dangerous(tc.name) and self.settings.safety.require_confirmation:
                await queue.put({
                    "type": "confirm_request",
                    "tool": tc.name,
                    "input": tc.input,
                    "tool_use_id": tc.id,
                })

                confirmed = await self._wait_for_confirmation(tc.id)
                if not confirmed:
                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": tc.id,
                        "content": "User denied this action.",
                        "is_error": True,
                    })
                    await queue.put({
                        "type": "tool_result",
                        "tool": tc.name,
                        "output": "Denied by user",
                        "success": False,
                    })
                    continue

            context.state = AgentState.TOOL_EXECUTING
            
            async def execute_tool():
                return await self.tools.execute(tc.name, tc.input)
                
            result = await self.self_healing.execute_with_retry(
                execute_tool,
                max_retries=1,
                context_msg=f"tool:{tc.name}"
            )

            await queue.put({
                "type": "tool_result",
                "tool": tc.name,
                "output": result.output[:500],
                "success": result.success,
            })

            tool_results.append({
                "type": "tool_result",
                "tool_use_id": tc.id,
                "content": result.to_content(),
                "is_error": not result.success,
            })

            # If the result contains multimodal content blocks (e.g., images),
            # the content field will be a list of dicts instead of a string.
            # Anthropic API accepts both formats natively.

        context.messages.append({
            "role": "user",
            "content": tool_results,
        })
        context.state = AgentState.THINKING
        
        return {"tool_calls": []}

    async def process(
        self,
        user_input: str,
        context: ConversationContext,
    ) -> AsyncGenerator[dict[str, Any], None]:
        self._interrupt.clear()
        context.state = AgentState.THINKING
        queue = asyncio.Queue()

        # Step 1: Memory
        memories = ""
        try:
            memories = await self.memory.get_context(user_input)
            if memories:
                await self.event_bus.emit(
                    Event(
                        type=EventType.MEMORY_RECALL,
                        data={"query": user_input, "memories": memories[:200]},
                        conversation_id=context.conversation_id,
                    )
                )
        except Exception as e:
            logger.warning("memory_recall_failed", error=str(e))

        # Step 2: Persona
        persona = ""
        try:
            prefs = await self.memory.long_term.get_all_preferences()
            if prefs:
                persona = "User preferences:\n" + "\n".join(f"- {k}: {v}" for k, v in prefs.items())
        except Exception as e:
            logger.warning("persona_recall_failed", error=str(e))

        context.messages.append({"role": "user", "content": user_input})
        system_prompt = build_system_prompt(memories=memories, persona=persona, tool_names=self.tools.list_tools())

        state: GraphState = {
            "context": context,
            "system_prompt": system_prompt,
            "queue": queue,
            "tool_calls": [],
            "iteration": 0,
            "user_input": user_input,
        }

        async def run_graph():
            try:
                await self.graph.ainvoke(state)
            except Exception as e:
                logger.error("graph_execution_failed", error=str(e))
                await queue.put({"type": "response_text", "text": f"\nSystem Error: {str(e)}"})
            finally:
                await queue.put(None)

        task = asyncio.create_task(run_graph())

        while True:
            item = await queue.get()
            if item is None:
                break
            yield item

        yield {"type": "response_done"}

    def interrupt(self) -> None:
        self._interrupt.set()
        logger.info("agent_interrupted")

    def _serialize_messages(self, messages: list[dict]) -> list[dict]:
        serialized = []
        for msg in messages:
            content = msg.get("content")
            if isinstance(content, str):
                serialized.append({"role": msg["role"], "content": content})
            elif isinstance(content, list):
                blocks = []
                for block in content:
                    if isinstance(block, dict):
                        blocks.append(block)
                    elif hasattr(block, "type"):
                        if block.type == "text":
                            blocks.append({"type": "text", "text": block.text})
                        elif block.type == "thinking":
                            blocks.append({"type": "thinking", "thinking": block.thinking})
                        elif block.type == "tool_use":
                            blocks.append({
                                "type": "tool_use",
                                "id": block.id,
                                "name": block.name,
                                "input": block.input,
                            })
                    else:
                        blocks.append(block)
                serialized.append({"role": msg["role"], "content": blocks})
            else:
                serialized.append(msg)
        return serialized

    async def _wait_for_confirmation(self, tool_use_id: str, timeout: float = 30.0) -> bool:
        confirmed = asyncio.Event()
        result = {"approved": False}

        async def on_confirm(event: Event):
            if event.data.get("tool_use_id") == tool_use_id:
                result["approved"] = event.data.get("approved", False)
                confirmed.set()

        self.event_bus.subscribe(EventType.CONFIRM_RESPONSE, on_confirm)
        try:
            await asyncio.wait_for(confirmed.wait(), timeout=timeout)
            return result["approved"]
        except asyncio.TimeoutError:
            return False
        finally:
            self.event_bus.unsubscribe(EventType.CONFIRM_RESPONSE, on_confirm)

    async def _store_interaction(self, user_input: str, response: str, context: ConversationContext) -> None:
        try:
            await self.memory.store(
                content=f"User: {user_input}\nMegan: {response}",
                memory_type="conversation",
                metadata={"conversation_id": context.conversation_id, "iterations": context.iteration_count},
            )
            await self.memory.process_feedback(user_input, response, context.conversation_id)
            
            # Asynchronously extract entities/facts (Mem0 behavior)
            asyncio.create_task(self.memory.extract_and_store(user_input))
        except Exception as e:
            logger.warning("memory_store_failed", error=str(e))
