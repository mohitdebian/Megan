<div align="center">
  <h1 align="center">MEGAN_OS</h1>
  <p align="center">
    <strong>A fully autonomous, voice-native, agentic operating system assistant.</strong>
    <br />
    <br />
    <a href="#features">Features</a>
    ·
    <a href="#architecture">Architecture</a>
    ·
    <a href="#getting-started">Getting Started</a>
    ·
    <a href="#tools">Tools</a>
  </p>
</div>

## What is Megan?
Megan is an advanced AI-native operating system designed to act as a **Jarvis-like** assistant. Instead of just answering questions, Megan actively operates your computer, browses the web, reads your codebase, answers your WhatsApp messages, and can even be remote-controlled from your phone via Telegram. 

Powered by **LangGraph V2** and advanced **Thinking Models**, Megan operates continuously, features real-time Voice-to-Voice (V2V) interruption capabilities, and sports a stunning real-time Desktop UI dashboard.

---

## 🔥 Features

- 🗣️ **Real-time Voice-to-Voice (V2V)**: Speak to Megan naturally. She listens constantly, streams high-fidelity TTS audio back instantly using ElevenLabs/Nvidia, and gracefully handles interruptions.
- 📱 **Telegram Remote Control**: Send a message to your Telegram bot while you are away from your laptop. Megan will execute the command on your machine in the background and reply directly to your phone.
- 💬 **Autonomous WhatsApp Bridge**: Megan connects to your WhatsApp, reads incoming messages, alerts you via voice if you are at the computer, and can auto-reply to specific "delegated" contacts using her Persona memory.
- 💻 **Computer Control Tools**: Deep integration with your OS. Megan can execute terminal commands, edit files, manage your clipboard, launch applications, and view system metrics.
- 🌐 **Web Browsing & Codebase Search**: Full browser control for complex web research, combined with codebase vector-search capabilities.
- 🧠 **Persistent Persona Memory**: Megan remembers details about you and the people you interact with. She maintains a persistent knowledge graph across sessions in her SQLite/ChromaDB memory bank.
- 🖥️ **Sci-Fi Desktop Dashboard**: A beautiful, real-time React UI that visualizes Megan's "Logic Stream", system metrics, active background tasks, and dynamically spawns "Windows" (like YouTube players, code snippets, or news feeds) onto the screen at her discretion.
- 🔄 **Background Workers**: Ask Megan to run long research tasks "in the background". She will spawn a detached reasoning thread and notify you via voice when she's done.

---

## 🏗️ Architecture

Megan consists of three main components:

1. **Backend (`/backend`)**: A **FastAPI** Python server that houses the `AgentBrain` (LangGraph state machine), handles WebSocket connections, manages ChromaDB vector memory, and integrates with TTS/STT APIs.
2. **Frontend (`/frontend`)**: A **React + Vite + TailwindCSS** web application that provides the futuristic Desktop UI. It connects to the backend via WebSockets.
3. **WhatsApp Bridge (`/whatsapp-bridge`)**: A lightweight **Node.js** server utilizing `whatsapp-web.js` that syncs WhatsApp events to the backend.

---

## 🚀 Getting Started

### Prerequisites
- **Python 3.10+**
- **Node.js 18+**
- **API Keys**: You will need keys for Claude/OpenAI (via proxy), Nvidia TTS or ElevenLabs, and optionally a Telegram Bot Token.

### 1. Clone the repository
```bash
git clone https://github.com/yourusername/megan-os.git
cd megan-os
```

### 2. Environment Setup
Copy the example environment file and fill in your keys:
```bash
cp .env.example .env
```
Ensure you provide a valid Telegram Chat ID and Bot Token if you want to use the remote control feature.

### 3. Backend Setup (FastAPI)
Navigate to the backend directory, install dependencies, and start the server:
```bash
cd backend
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python main.py
```
*The backend runs on `http://localhost:8000`.*

### 4. Frontend Setup (React/Vite)
Open a new terminal, navigate to the frontend directory, install packages, and start the UI:
```bash
cd frontend
npm install
npm run dev
```
*The frontend runs on `http://localhost:5173`.*

### 5. WhatsApp Bridge Setup (Optional)
If you want WhatsApp integration, start the Node.js bridge in a separate terminal:
```bash
cd whatsapp-bridge
npm install
node server.js
```
Scan the QR code printed in the terminal to link your WhatsApp account.

---

## 🛠️ Tools

Megan is equipped with a massive suite of tools to interact with the world:

| Tool | Description | Dangerous? |
|------|-------------|:----------:|
| `terminal` | Execute arbitrary shell commands | ⚠️ Yes |
| `filesystem` | Read/write/list/search files | No |
| `web_search` | Search the web autonomously | No |
| `browser` | Fetch and read web pages | No |
| `code_executor` | Run Python/JS/Bash code | ⚠️ Yes |
| `clipboard` | Read/write system clipboard | No |
| `app_launcher` | Open apps and files on the host OS | No |
| `system_info` | CPU, memory, disk, processes | No |
| `codebase` | Repository vector search + analysis | No |
| `whatsapp` | Send/Reply to WhatsApp messages | No |
| `telegram` | Send messages to the user via Telegram | No |
| `background_worker` | Spawn detached agent threads | No |
| `persona` | Store/recall long-term memories | No |
| `window` | Spawn UI windows on the Desktop dashboard | No |

---

## 🔒 Safety & Permissions
Megan can run arbitrary terminal commands and modify your filesystem. **Use with caution.** 
By default, destructive commands will trigger a "Confirmation Request" that pops up in the UI, requiring you to click "Approve" or "Deny" before Megan can execute them.

## 📄 License
This project is licensed under the [MIT License](LICENSE). Feel free to fork, modify, and build your own JARVIS!
