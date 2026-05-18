/**
 * MeganShell — holographic circular interface.
 * Centered orb | sidebar nav | clean panels.
 */

import { useState, useRef, type KeyboardEvent } from 'react';
import { useMegan } from '../hooks/useMegan';
import { Transcript } from './Transcript';
import { LogicStream } from './LogicStream';
import { SystemDashboard } from './SystemDashboard';
import { KnowledgeBase } from './KnowledgeBase';
import { VoiceOrb } from './VoiceOrb';
import { Desktop } from './Desktop';

const NAV_ITEMS = [
  { id: 'chat', label: 'CHAT' },
  { id: 'desktop', label: 'DESKTOP' },
  { id: 'system', label: 'SYSTEM' },
  { id: 'knowledge', label: 'MEMORY' },
];

export function MeganShell() {
  const megan = useMegan();
  const [input, setInput] = useState('');
  const [activeNav, setActiveNav] = useState('chat');
  const inputRef = useRef<HTMLInputElement>(null);

  const handleSend = () => {
    if (input.trim()) {
      megan.sendText(input);
      setInput('');
    }
  };

  const handleKeyDown = (e: KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  return (
    <div className="h-screen w-screen bg-megan-bg flex font-mono text-megan-text overflow-hidden holo-scan relative">
      {/* ═══ LEFT SIDEBAR ═══ */}
      <aside className="w-44 border-r border-megan-border flex flex-col bg-megan-surface shrink-0">
        {/* Brand */}
        <div className="px-4 py-5 border-b border-megan-border flex items-center gap-3">
          <div className="w-8 h-8 rounded-full border border-megan-cyan/30 flex items-center justify-center">
            <span className="text-sm text-megan-cyan font-bold">M</span>
          </div>
          <div>
            <h1 className="text-sm font-bold tracking-widest text-megan-cyan">MEGAN</h1>
            <p className="text-[9px] text-megan-text-muted tracking-wider">ONLINE</p>
          </div>
        </div>

        {/* Voice Orb — centered */}
        <div className="py-6 flex justify-center border-b border-megan-border">
          <VoiceOrb
            state={megan.state}
            onClick={megan.toggleConversationMode}
            isRecording={megan.conversationMode}
          />
        </div>

        {/* Navigation */}
        <nav className="flex-1 py-2">
          {NAV_ITEMS.map((item) => (
            <button
              key={item.id}
              onClick={() => setActiveNav(item.id)}
              className={`nav-item w-full flex items-center px-5 py-2.5 text-left text-[11px] tracking-wider transition-all ${
                activeNav === item.id
                  ? 'active text-megan-cyan'
                  : 'text-megan-text-dim hover:text-megan-text'
              }`}
            >
              <span>{item.label}</span>
            </button>
          ))}
        </nav>

        {/* Voice toggle */}
        <div className="px-4 py-3 border-t border-megan-border">
          <button
            onClick={megan.toggleVoiceOutput}
            className="w-full flex items-center justify-between text-[10px] tracking-wider text-megan-text-muted hover:text-megan-text transition-colors"
          >
            <span>VOICE {megan.voiceEnabled ? 'ON' : 'OFF'}</span>
            <span
              className={`w-2 h-2 rounded-full ${megan.voiceEnabled ? 'bg-megan-green dot-pulse' : 'bg-megan-text-muted'}`}
            />
          </button>
        </div>

        {/* Connection */}
        <div className="px-4 py-2 border-t border-megan-border">
          <div className="flex items-center gap-2">
            <span
              className={`w-1.5 h-1.5 rounded-full ${megan.connected ? 'bg-megan-green dot-pulse' : 'bg-megan-rose'}`}
            />
            <span className="text-[9px] text-megan-text-muted tracking-wider">
              {megan.connected ? 'CONNECTED' : 'DISCONNECTED'}
            </span>
          </div>
        </div>
      </aside>

      {/* ═══ CENTER — MAIN CONTENT ═══ */}
      <div className="flex-1 flex flex-col min-w-0">
        {/* Top status bar */}
        <header className="flex items-center justify-between px-5 py-2 border-b border-megan-border bg-megan-surface">
          <div className="flex items-center gap-4 text-[10px] tracking-wider">
            <span className="text-megan-text-dim">v1.0</span>
            <span className="flex items-center gap-1.5">
              <span className="w-1 h-1 rounded-full bg-megan-green dot-pulse" />
              <span className="text-megan-text-dim">CPU 12%</span>
            </span>
            <span className="flex items-center gap-1.5">
              <span className="w-1 h-1 rounded-full bg-megan-cyan dot-pulse" />
              <span className="text-megan-text-dim">MEM 48%</span>
            </span>
          </div>
          <div className="text-[10px] text-megan-text-muted tracking-wider">
            {megan.conversationMode
              ? (megan.isSpeaking ? 'RECORDING' : megan.state === 'thinking' ? 'PROCESSING' : 'LISTENING')
              : megan.state === 'idle'
              ? 'IDLE'
              : megan.state.toUpperCase().replace('_', ' ')}
          </div>
        </header>

        {/* Content area */}
        <div className="flex-1 overflow-hidden relative">
          {activeNav === 'chat' && (
            <Transcript entries={megan.transcript} currentResponse={megan.currentResponse} />
          )}
          {activeNav === 'desktop' && (
            <Desktop 
              windows={megan.activeWindows} 
              onFocusWindow={(id) => {
                 megan.setActiveWindows(prev => prev.map(w => w.id === id ? { ...w, zIndex: Math.max(...prev.map(p => p.zIndex), 10) + 1 } : w));
              }}
              onCloseWindow={(id) => {
                 megan.setActiveWindows(prev => prev.filter(w => w.id !== id));
              }}
            />
          )}
          {activeNav === 'system' && (
            <SystemDashboard 
              backgroundLogicStream={megan.backgroundLogicStream}
              backgroundTranscript={megan.backgroundTranscript}
            />
          )}
          {activeNav === 'knowledge' && <KnowledgeBase />}
          {activeNav === 'logic' && (
            <div className="h-full lg:hidden">
              <LogicStream entries={megan.logicStream} />
            </div>
          )}
        </div>

        {/* Input bar */}
        <div className="px-5 py-3 border-t border-megan-border bg-megan-surface">
          {megan.conversationMode && (
            <div className="flex items-center gap-2 mb-2">
              <span className="w-1.5 h-1.5 rounded-full bg-megan-cyan animate-pulse" />
              <span className="text-[9px] text-megan-text-muted tracking-wider">
                {megan.isSpeaking ? 'SPEECH DETECTED' : 'CONVERSE MODE — SPEAK ANYTIME'}
              </span>
            </div>
          )}
          <div className="flex items-center gap-3">
            <span className="text-megan-cyan text-[10px]">&gt;</span>
            <input
              ref={inputRef}
              id="text-input"
              type="text"
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={handleKeyDown}
              placeholder="Type a command..."
              className="flex-1 bg-transparent text-sm text-megan-text placeholder:text-megan-text-muted outline-none tracking-wide"
            />
            <button
              id="send-button"
              onClick={handleSend}
              disabled={!input.trim()}
              className="px-3 py-1 text-[10px] tracking-wider border border-megan-border text-megan-text-dim hover:text-megan-cyan hover:border-megan-cyan disabled:opacity-20 transition-all"
            >
              SEND
            </button>
            {megan.state !== 'idle' && megan.state !== 'listening' && (
              <button
                id="interrupt-button"
                onClick={megan.interrupt}
                className="px-3 py-1 text-[10px] tracking-wider border border-megan-rose/30 text-megan-rose/70 hover:text-megan-rose hover:border-megan-rose transition-all"
              >
                STOP
              </button>
            )}
          </div>
        </div>
      </div>

      {/* ═══ RIGHT SIDEBAR — LOGIC STREAM ═══ */}
      <aside className="w-64 border-l border-megan-border flex flex-col bg-megan-surface shrink-0 hidden lg:flex">
        <div className="px-4 py-2.5 border-b border-megan-border flex items-center justify-between">
          <h2 className="text-[10px] tracking-[0.2em] text-megan-cyan">LOGIC STREAM</h2>
          <span className="text-[9px] text-megan-text-muted">YOUR TASKS</span>
        </div>
        <div className="flex-1 overflow-hidden">
          <LogicStream entries={megan.logicStream} />
        </div>
        <div className="border-t border-megan-border px-4 py-2">
          <div className="text-[9px] text-megan-text-muted tracking-wider">
            {megan.availableTools.length} TOOLS AVAILABLE
          </div>
        </div>
      </aside>

      {/* ═══ CONFIRMATION MODAL ═══ */}
      {megan.confirmRequest && (
        <div className="absolute inset-0 bg-black/70 flex items-center justify-center z-50">
          <div className="bg-megan-surface rounded-xl border border-megan-border p-6 max-w-md ring-glow animate-fade-in">
            <h3 className="text-[10px] tracking-[0.2em] text-megan-rose mb-4">
              CONFIRM ACTION
            </h3>
            <p className="text-xs text-megan-text mb-3">
              Execute <span className="text-megan-cyan font-bold">{megan.confirmRequest.tool.toUpperCase()}</span>?
            </p>
            <pre className="text-[10px] bg-megan-bg p-3 rounded-lg border border-megan-border mb-5 text-megan-text-dim overflow-x-auto leading-relaxed">
              {JSON.stringify(megan.confirmRequest.input, null, 2)}
            </pre>
            <div className="flex gap-2 justify-end">
              <button
                id="deny-button"
                onClick={() => megan.respondToConfirm(false)}
                className="px-4 py-1.5 text-[10px] tracking-wider border border-megan-rose/30 text-megan-rose hover:bg-megan-rose/10 rounded transition-all"
              >
                DENY
              </button>
              <button
                id="approve-button"
                onClick={() => megan.respondToConfirm(true)}
                className="px-4 py-1.5 text-[10px] tracking-wider border border-megan-green/30 text-megan-green hover:bg-megan-green/10 rounded transition-all"
              >
                APPROVE
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
