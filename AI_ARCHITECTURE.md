# Megan AI Architecture Guide

Megan is not just a standard chatbot; she is an autonomous, agentic operating system. This document explains how her "Brain" works, how she communicates with the LLM API, and how you can configure the backend.

## 🧠 The Agent Brain (LangGraph V2)

Megan's reasoning engine is powered by **LangGraph V2**, a state machine framework designed for building highly autonomous, multi-step AI agents.

### The Loop
1. **Input Reception**: You speak to Megan, type in the UI, or send a Telegram message.
2. **Context Assembly**: Megan pulls your previous conversation history, fetches relevant context from her persistent memory (ChromaDB), and loads your `Persona` data.
3. **System Prompt Formulation**: A massive, dynamic system prompt is built containing your OS rules, available tools (in JSON Schema format), and current state.
4. **LLM Evaluation**: The state is sent to the LLM proxy.
5. **Tool Execution**: If the LLM decides to take action (e.g., run a shell command, read a file), it yields a `tool_use` block. Megan executes the tool locally.
6. **Re-evaluation**: The result of the tool is appended to the context, and the loop repeats (Step 4) until the LLM decides the task is fully complete and generates a final text response.

## 🔌 The LLM Proxy Setup

Because Megan requires advanced reasoning and "thinking" capabilities, we heavily rely on top-tier models (like Anthropic's Claude 3.5 Sonnet or DeepSeek). 

Instead of hardcoding API keys for a single provider, Megan routes all her intelligence through a **Local Proxy** (like `litellm` or a custom proxy server). This allows you to hot-swap models without changing Megan's core code.

### Configuration (`.env`)
```env
CLAUDE_BASE_URL=http://localhost:8082
CLAUDE_AUTH_TOKEN=your_auth_token_here
CLAUDE_MODEL=anthropic/your_model_name_here
```

### Why a Proxy?
- **Cost Management**: You can route requests to cheaper models for simple tasks and expensive models for complex tasks.
- **Protocol Standardization**: The proxy ensures all API responses strictly follow the standard structure expected by Megan's LangGraph integration.
- **Thinking Blocks**: Advanced models yield `<thinking>` blocks before they act. The proxy passes these blocks down, allowing Megan to display her live thoughts on the Desktop UI before she executes a tool.

## 🛠️ Tool Invocation Protocol

When Megan wants to communicate with your OS, she doesn't type raw bash commands immediately. She uses a strict JSON schema protocol.

1. **Schema Delivery**: On startup, `backend/tools/registry.py` dumps every available tool into a schema (e.g., `web_search`, `terminal`, `browser`).
2. **Action Intent**: The LLM responds with a JSON payload specifying the `tool_name` and `parameters`.
3. **Safety Gating**: If the tool is marked as `dangerous=True` (like `terminal` or `code_executor`), Megan pauses the LangGraph execution. An event is emitted to the UI via WebSockets asking you to **Confirm** or **Deny** the action.
4. **Execution**: Once approved, the Python backend executes the action on your host machine and feeds the exact terminal stdout/stderr back to the LLM.

## 💾 Memory & RAG

Megan doesn't just read the last 5 messages; she remembers *everything*.
- **Short-Term Memory**: Kept in RAM during the session.
- **Long-Term Persona**: Stored in a local SQLite database (`data/memory.db`). She autonomously adds facts about you, your friends, and your preferences using her `persona` tool.
- **RAG Vector Search**: When you ask her to analyze your codebase, she chunks your files using AST parsing (`backend/rag/chunker.py`) and stores the embeddings in a local ChromaDB instance. When answering, she does a semantic search to find the exact lines of code she needs.
