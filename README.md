<div align="center">
  <img src="https://raw.githubusercontent.com/mohitdebian/Megan/main/frontend/public/megan-logo.png" alt="Megan OS Logo" width="150" />
  <h1 align="center">MEGAN OS</h1>
  <p align="center">
    <strong>A fully autonomous, voice-native, agentic operating system assistant.</strong>
    <br />
    <br />
    <a href="#overview">Overview</a>
    ·
    <a href="#core-capabilities">Core Capabilities</a>
    ·
    <a href="#architecture">Architecture</a>
    ·
    <a href="#installation-guide">Installation</a>
    ·
    <a href="#tool-reference">Tool Reference</a>
  </p>
</div>

---

## 🌌 Overview

Megan is not a simple chatbot; she is an advanced AI-native operating system built to act as a fully autonomous **Jarvis-like assistant**. Designed to seamlessly blend into your physical and digital environment, Megan actively operates your computer, controls your smart home devices, manages your local media, monitors network security, and acts as a bridge for your social communications.

Powered by **LangGraph V2** and advanced **Thinking Models**, Megan operates continuously in the background, features real-time Voice-to-Voice (V2V) interruption capabilities, and sports a stunning Sci-Fi inspired React UI dashboard.

---

## 🔥 Core Capabilities & Features

### 1. Voice-Native Interaction & Real-Time UI
*   **Real-time Voice-to-Voice (V2V):** Speak to Megan naturally. She listens constantly via WebSockets, streams high-fidelity TTS audio back instantly using ElevenLabs or Nvidia engines, and gracefully handles conversational interruptions.
*   **Sci-Fi Desktop Dashboard:** A beautiful, real-time React UI that visualizes Megan's internal "Logic Stream", system metrics, and active background tasks. Megan can dynamically spawn "Windows" (like YouTube players, code snippets, maps, or news feeds) directly onto the screen at her discretion.

### 2. Autonomous Environment Orchestration (Smart Home)
Megan maps and controls the physical room she is in using a persistent `DeviceManager`.
*   **Persistent Device Intelligence:** Instead of scanning the network for every request, Megan maintains a persistent registry of all LAN devices. She tracks MAC addresses, caches IP connections, and performs 30-second health pings to instantly know when a device turns on or off.
*   **Fuzzy Matching & Auto-routing:** You don't need exact IP addresses. Say *"Pause the QLED"* or *"Mute the TV"* and Megan uses fuzzy logic to route the command to the correct physical device.
*   **Advanced Scene Engine:** Built-in support for chained actions, delays, and state rollbacks. 
    *   *Movie Mode:* Dims the dashboard UI, sets TV volume to 30%, and sends a phone notification.
    *   *Sleep Mode:* Lowers TV volume to 5%, waits 2 seconds, and stops playback entirely.
    *   *Auto-Deactivate:* If a device goes offline unexpectedly, Megan rolls back the active scene automatically.

### 3. Unified Local Media Ecosystem
Megan serves as a personalized streaming server for your local files and online content.
*   **Local Media Indexing:** Automatically scans your `~/Videos`, `~/Movies`, `~/Downloads`, and `~/Music` directories. Uses `ffprobe` to extract metadata (duration, resolution, codecs).
*   **Watch History & Resume:** If you stop casting a movie halfway through, Megan remembers exactly where you left off. Ask her to *"Resume the Matrix movie"* and it starts from the exact timestamp.
*   **Live YouTube Search & Cast:** Using an ad-free Invidious API proxy, Megan can autonomously search YouTube for queries like *"Play Bollywood music"*, grab the exact `videoId`, and cast it to your TV automatically.
*   **Live Desktop Screencasting:** Megan can mirror your Linux desktop to your TV. She uses a custom Python `mss` loop to grab raw pixel frames, piping them dynamically into `ffmpeg` to encode a low-latency HTTP Live Stream (HLS) that your Chromecast can connect to.

### 4. Cybersecurity & Network Intelligence
Megan passively acts as a guardian for your local network.
*   **ARP Topology Mapping:** She constantly sniffs the system ARP table to map every connected device in real-time.
*   **Non-Intrusive Fingerprinting:** She runs localized port scans to categorize devices (e.g., Apple Airplay, Media Server, Generic Web Device).
*   **Trust Scoring:** Devices are given a trust score out of 100 based on their MAC address history. If a new, unknown device joins your network, Megan's `AutomationEngine` will trigger an immediate alert.

### 5. Memory & Autonomous Behaviors
*   **Device Preferences Memory:** Megan learns your habits. She remembers your preferred default TV, the average volume you listen at, and the scenes you trigger most often.
*   **System Heartbeat:** A background cron-like service that runs autonomously. It triggers media library rescans every 6 hours, network topology snapshots every 24 hours, and handles late-night volume reminders.
*   **Persona Knowledge Graph:** Megan remembers personal details about you and the people you interact with. She maintains a persistent knowledge graph across sessions in her SQLite/ChromaDB memory bank.

### 6. Delegated Communication
*   **Autonomous WhatsApp Bridge:** Megan connects to your WhatsApp. She reads incoming messages, alerts you via voice if you are at the computer, and can auto-reply to specific "delegated" contacts using her Persona memory.
*   **Telegram Remote Control:** Send a message to your Telegram bot while you are away. Megan will execute the command on your laptop in the background and reply directly to your phone.

### 7. Autonomous Importance Monitor
Megan acts as your personal secretary, filtering the noise from your digital life.
*   **Priority Classifier:** Every incoming WhatsApp message and email is silently evaluated by a lightweight AI classifier on a scale of 1-10. Only messages scoring 7+ are announced aloud via TTS.
*   **Email Monitor:** A background IMAP service polls your inbox every 60 seconds. When a high-priority email arrives (e.g., from your boss, a financial alert, or a direct question), Megan announces the sender and subject.
*   **Smart Filtering:** Spam, newsletters, and casual chatter are silently ignored. Your focus is protected.

### 8. Proactive Morning Briefing & OSINT
Megan compiles a personalized daily brief and delivers it when you sit down.
*   **Autonomous Compilation:** At 8:00 AM, the `SystemHeartbeat` triggers the `MorningRoutine` service. It spawns a background agent that checks your unread emails, searches the web for top tech/AI news, and reads your persona memory for reminders.
*   **First-Connect Delivery:** The compiled brief is stored until you open the Megan dashboard. The moment the WebSocket connects, Megan greets you: *"Good morning, Sir. You have 5 unread emails..."*

### 9. Self-Healing Code & Autonomous Debugger
Megan watches your code sandbox and fixes crashes before you even notice them.
*   **File Watcher:** Using `watchdog`, Megan monitors `~/projects/sandbox/` for `.py` file saves. When a file is saved, she automatically runs it in a subprocess.
*   **Healer Agent:** If the script exits with a traceback (TypeError, ImportError, etc.), the `HealerAgent` reads the source + error, sends it to the LLM for a patch, writes the fix back, and re-runs to verify. If successful, she announces: *"Sir, your script crashed, but I've already patched it."*
*   **Safe Rollback:** If the LLM's patch introduces a *new* error, Megan automatically rolls back to the original file from a `.bak` backup.

### 10. Multi-Agent Swarm (Delegation)
Megan can orchestrate specialized sub-agents for complex tasks.
*   **CEO Architecture:** When you ask Megan to write a detailed report, she doesn't do everything herself. She uses the `delegate_task` tool to spawn a pipeline of specialized agents.
*   **Researcher Agent:** Equipped only with `web_search`. It generates focused queries, executes them via DuckDuckGo, and synthesizes raw research notes.
*   **Writer Agent:** Takes the research notes and drafts a polished, structured markdown report (with executive summary, key findings, analysis, and conclusion). Saves it to `~/Documents/`.
*   **Background Execution:** The entire pipeline runs asynchronously. Megan notifies you via TTS when the report is ready.

---

## 🏗️ Technical Architecture

Megan's architecture is highly decoupled, event-driven, and relies on Dependency Injection for seamless testing and extensibility.

### System Components

1.  **Backend (`/backend`)**: A **FastAPI** Python server that houses the `AgentBrain` (LangGraph state machine).
    *   **EventBus:** A centralized pub/sub system. Services (like `LANMonitor`, `MediaLibrary`) emit events (e.g., `DEVICE_OFFLINE`), which the `AutomationEngine` listens to.
    *   **MemoryManager:** Handles Short-Term (conversational context), Long-Term (SQLite structured data), Semantic (ChromaDB vector embeddings), and Device Preferences memory.
    *   **Lifespan Management:** Uses a DI `Container` to ensure background workers (Heartbeat, Network Scanners) initialize safely on boot and shutdown cleanly.

2.  **Frontend (`/frontend`)**: A **React + Vite + TailwindCSS** SPA.
    *   **WebSocket Link:** Connects to the backend for real-time state updates, UI window spawning, and voice streaming.
    *   **Audio Engine:** Uses `AudioContext` to handle bidirectional V2V streaming with proper echo cancellation and VAD (Voice Activity Detection).

3.  **WhatsApp Bridge (`/whatsapp-bridge`)**: A **Node.js** microservice using `whatsapp-web.js`.
    *   Syncs WhatsApp events to the FastAPI backend via HTTP webhooks.

---

## 🚀 Installation & Setup Guide

### Prerequisites
- **OS:** Linux (Ubuntu/Debian recommended for full OS integration).
- **Python:** 3.10 or higher.
- **Node.js:** 18 or higher.
- **Packages:** `ffmpeg` (required for media streaming and screencasting).
- **API Keys:** Claude/OpenAI (for the reasoning engine), ElevenLabs (for TTS), and optionally a Telegram Bot Token.

### Step 1: Clone the Repository
```bash
git clone https://github.com/mohitdebian/Megan.git
cd Megan
```

### Step 2: Environment Configuration
Copy the template and fill in your keys.
```bash
cd backend
cp .env.example .env
```
Ensure you provide a valid `OPENAI_API_KEY` (or equivalent proxy) and `ELEVENLABS_API_KEY`. If you want remote control, add your `TELEGRAM_BOT_TOKEN`.

### Step 3: Backend Setup
Install system dependencies (if on Debian/Ubuntu):
```bash
sudo apt update
sudo apt install ffmpeg
```

Set up the Python virtual environment and run the server:
```bash
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

### Step 4: Frontend Setup
In a new terminal window, start the Vite development server:
```bash
cd frontend
npm install
npm run dev
```
Open your browser to `http://localhost:5173`. You should see the Megan OS Dashboard.

### Step 5: WhatsApp Bridge (Optional)
If you wish to enable WhatsApp integration:
```bash
cd whatsapp-bridge
npm install
node server.js
```
Scan the QR code printed in the terminal with your phone to link the bridge.

---

## 🛠️ Comprehensive Tool Reference

Megan is equipped with a massive suite of tools to interact with the world. The LLM agent autonomously decides when and how to use these tools based on your requests.

| Tool | Category | Description | Dangerous? |
|------|----------|-------------|:----------:|
| `chromecast` | Environment | Control Google Cast devices (play, pause, volume). Search and cast YouTube videos. Live screencast the desktop. | No |
| `scene_manager` | Environment | Activate orchestrated room scenes (Movie, Gaming, Sleep, etc.) | No |
| `media_tool` | Environment | Search local media library, resume watched videos, get AI recommendations. | No |
| `security_tool` | Network | Generate network trust reports, show LAN topology, port scan devices. | No |
| `terminal` | System | Execute arbitrary shell (Bash) commands on the host OS. | ⚠️ Yes |
| `filesystem` | System | Read, write, list, and search files locally. | No |
| `app_launcher` | System | Open desktop applications and files. | No |
| `system_info` | System | Fetch CPU, memory, disk usage, and process lists. | No |
| `screen_vision` | Vision | Takes a screenshot of the desktop using `mss` and sends it to the vision model for analysis. | No |
| `web_search` | Internet | Search the web autonomously via DuckDuckGo/Tavily. | No |
| `browser` | Internet | Fetch and read web pages, bypass basic anti-bot screens. | No |
| `codebase` | Dev | Semantic vector search across the entire Megan codebase. | No |
| `code_executor` | Dev | Run Python/JS code in an isolated subprocess. | ⚠️ Yes |
| `whatsapp` | Comms | Send or reply to WhatsApp messages. | No |
| `telegram` | Comms | Send messages to the user via Telegram. | No |
| `background_worker`| Core | Spawn detached reasoning threads for long tasks. | No |
| `persona` | Core | Store and recall long-term memories in ChromaDB. | No |
| `window` | Core | Spawn UI windows on the React Desktop dashboard. | No |
| `delegate_task` | Swarm | Orchestrate Researcher + Writer sub-agents for deep research & report writing. | No |
| `youtube` | Media | Search YouTube via Invidious API and return video IDs for casting. | No |

---

## 🔒 Safety & Permissions

Megan is designed to be an **agentic OS**, which means she has the ability to run arbitrary terminal commands, modify your filesystem, and interact with the local network. 

**Use with caution.** 

By default, any destructive commands (via `terminal` or `code_executor`) will trigger a **Confirmation Request**. This request will pop up in the React UI, pausing the agent's execution thread, and requiring you to explicitly click "Approve" or "Deny" before Megan can execute the command. Do not disable this safeguard unless you are running Megan in an isolated VM or container.

---

## 📄 License
This project is licensed under the [MIT License](LICENSE). Feel free to fork, modify, and build your own autonomous JARVIS!
