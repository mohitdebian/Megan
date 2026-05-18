# Megan OS: Codebase Wiki

Welcome to the Megan OS Codebase Wiki. This document serves as a comprehensive map of the entire project, detailing how the backend, frontend, and external services communicate to create a seamless, real-time AI operating system.

---

## 📂 High-Level Directory Structure

The repository is split into three primary domains:

```text
megan/
├── backend/           # Core AI Engine (Python + FastAPI)
├── frontend/          # Desktop UI Dashboard (React + Vite + Tailwind)
└── whatsapp-bridge/   # WhatsApp Integration Server (Node.js)
```

---

## 🐍 1. Backend (`/backend`)
The backend is the true "Brain" of Megan. It handles LLM orchestration, voice synthesis (TTS), speech-to-text (STT), memory retrieval, and operating system tool execution.

### Entry Points & Core
- `main.py`: The FastAPI entry point. It initializes all services (via `dependencies.py`), mounts REST/WebSocket routes, and starts background listeners (like the Telegram listener).
- `config.py`: Centralized configuration management using Pydantic Settings. All `.env` variables are strictly typed here.
- `core/dependencies.py`: The Dependency Injection (DI) container. Heavy services (like ChromaDB, Whisper STT) are loaded lazily here as singletons.
- `core/events.py`: The **Async Event Bus**. Megan is entirely event-driven. Instead of components calling each other, they emit events (e.g., `THINKING`, `TOOL_START`, `SYSTEM_NOTIFICATION`) which are broadcasted to the frontend via WebSockets.

### The Agent (`backend/agent`)
This is the reasoning engine powered by LangGraph.
- `brain.py`: Defines the `AgentBrain` state machine. It handles the loop of receiving input, calling the LLM proxy, executing tools, and yielding results back.
- `system_prompt.py`: Generates the massive master prompt that dictates Megan's personality, rules, and restrictions.
- `context_compressor.py`: Ensures the context window doesn't overflow by intelligently summarizing older messages.

### Tools (`backend/tools`)
Megan interacts with the world via Tools.
- `registry.py`: The central registry. It takes Python classes and automatically converts them into JSON schemas for the LLM.
- **Notable Tools**:
  - `terminal.py` / `code_executor.py`: Allows Megan to run arbitrary bash commands or Python scripts. (Gated by Safety Confirmation).
  - `browser.py` / `web_search.py`: For fetching external information.
  - `background_worker.py`: Spawns a detached `AgentBrain` thread to perform long-running tasks without blocking the main conversation.
  - `whatsapp.py` / `telegram.py`: External communication channels.

### Memory & RAG (`backend/memory` & `backend/rag`)
- `memory/manager.py`: Orchestrates both short-term (RAM) and long-term memory.
- `memory/semantic.py`: Uses ChromaDB for vector-based semantic retrieval of past conversations and persona facts.
- `rag/chunker.py` & `indexer.py`: Uses AST (Abstract Syntax Trees) to intelligently chunk your code repository into searchable vectors, allowing Megan to read and edit your code accurately.

### Audio Pipeline (`backend/audio`)
- `stt_service.py`: Uses `faster-whisper` (GPU-accelerated) to transcribe incoming base64 audio chunks.
- `tts_service.py`: Streams text to Nvidia Magpie or ElevenLabs APIs and yields raw audio bytes.
- `stream_manager.py`: Orchestrates the flow of VAD (Voice Activity Detection) interruptions, buffering, and async audio generation.

---

## 🖥️ 2. Frontend (`/frontend`)
The frontend is a Sci-Fi inspired React application that connects to the backend exclusively via WebSockets for real-time, bi-directional streaming.

### Core Components
- `App.tsx`: The root application wrapper.
- `components/MeganShell.tsx`: The primary layout. It renders the Sidebar, Topbar, and central content area.
- `components/Desktop.tsx`: The "OS" view. It manages absolutely positioned `Window` components that Megan can spawn autonomously (like News feeds, YouTube players, or Weather widgets).

### State & Logic (`src/hooks`)
- `useWebSocket.ts`: Manages the WebSocket connection to the Python backend. It handles auto-reconnection and routes incoming events to the UI.
- `useMegan.ts`: The central state store. It listens to WebSocket events and updates React state (e.g., `isSpeaking`, `transcript`, `logicStream`, `activeWindows`).
- `useVAD.ts`: Uses `@ricky0123/vad-web` for in-browser Voice Activity Detection. When you start speaking, it interrupts Megan's current speech. When you stop, it captures the audio and sends it to the backend for STT.

### The Logic Stream
Megan is highly transparent. The `LogicStream.tsx` and `ToolFeed.tsx` components visually render the `<thinking>` blocks and tool executions yielded by the LangGraph brain in real-time, giving you a live look into her reasoning.

---

## 💬 3. WhatsApp Bridge (`/whatsapp-bridge`)
Because WhatsApp doesn't have an open API for personal accounts, Megan uses a dedicated Node.js bridge.

- `server.js`: Uses `whatsapp-web.js` to run a headless Chromium browser. It syncs your phone via a QR code and listens for incoming messages.
- **Data Flow**: When a message arrives, the Node.js server sends a POST request to the Python backend's REST API (`api/routes.py`). The backend then emits a `SYSTEM_NOTIFICATION` event, alerting the `AgentBrain` or speaking the notification aloud on the frontend.
- **Delegation**: If a contact is flagged as "delegated" in Megan's SQLite database, she will autonomously use the `whatsapp` tool to reply to them without your intervention.

---

## 🔄 Data Flow Summary: "A Complete Turn"

1. **User Speaks**: You say "Open YouTube".
2. **VAD Triggers**: The frontend `useVAD` detects speech end, converts it to base64, and sends `{"type": "audio_file"}` via WebSocket.
3. **Backend Transcription**: `websocket.py` receives the audio, passes it to `stream_manager.py`, which uses Whisper to get the text: "Open YouTube".
4. **Agent Processing**: The text enters `agent_brain.process()`. 
5. **Thinking & Tool Selection**: The LLM proxy streams back a `<thinking>` block. The backend emits this via `EventBus`, and the frontend renders it in the `LogicStream`.
6. **Tool Execution**: The LLM calls the `window` tool with action `spawn_window` and URL `youtube.com`. 
7. **UI Update**: The backend emits the `TOOL_START` event. `useMegan.ts` intercepts this and updates `setActiveWindows`, instantly popping a YouTube window on your screen.
8. **Final Response**: The LLM generates "I've opened YouTube for you."
9. **TTS Streaming**: The text is sent to ElevenLabs. Audio bytes stream back to the frontend and are played via `audioUtils.ts`.

---

## 🛠️ How to Extend Megan

- **Add a Tool**: Create a new class in `backend/tools/`, inherit from `BaseTool`, define `parameters` JSON schema, and register it in `core/dependencies.py`.
- **Add a UI Window**: Add a new component in `frontend/src/components/windows/`, update the `Window.tsx` switch statement to render it, and instruct Megan to use it via the system prompt.
- **Add a Notification Channel**: Look at `backend/telegram_listener.py` as an example of how to inject background events directly into a fresh `AgentBrain` context.
