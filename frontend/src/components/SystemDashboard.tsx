/**
 * SystemDashboard — HUD-style system operations panel.
 * Shows delegated WhatsApp contacts, auto-handled messages, background tasks, and system metrics.
 */

import { useEffect, useState } from 'react';

interface SystemMetrics {
  cpu_percent: number;
  memory_percent: number;
  memory_used_gb: number;
  memory_total_gb: number;
  disk_percent: number;
}

interface BackgroundTask {
  id: string;
  description: string;
  status: string;
  elapsed_seconds: number;
  result: string | null;
  error: string | null;
}

interface AutoHandledMessage {
  name: string;
  number: string;
  body: string;
  handled_at: string;
}

interface ThoughtEvent {
  type: string;
  data: Record<string, unknown>;
  timestamp: string;
}

interface ThoughtStream {
  conversation_id: string;
  name: string;
  number: string;
  events: ThoughtEvent[];
  started_at: string;
  updated_at: string;
}

interface SystemOpsData {
  delegated_contacts: string[];
  auto_handled_messages: AutoHandledMessage[];
  background_tasks: BackgroundTask[];
  background_thought_streams: ThoughtStream[];
  timestamp: string;
}

const API_BASE = `http://${window.location.hostname}:8000/api`;

import { LogicStream } from './LogicStream';
import type { LogicEntry, TranscriptEntry } from '../types';

interface SystemDashboardProps {
  backgroundLogicStream?: LogicEntry[];
  backgroundTranscript?: TranscriptEntry[];
}

export function SystemDashboard({ backgroundLogicStream = [], backgroundTranscript = [] }: SystemDashboardProps) {
  const [metrics, setMetrics] = useState<SystemMetrics | null>(null);
  const [ops, setOps] = useState<SystemOpsData | null>(null);

  useEffect(() => {
    const fetchData = async () => {
      try {
        const [sysRes, opsRes] = await Promise.all([
          fetch(`${API_BASE}/system`),
          fetch(`${API_BASE}/system-ops`),
        ]);
        setMetrics(await sysRes.json());
        setOps(await opsRes.json());
      } catch (e) {
        console.error('Dashboard fetch error:', e);
      }
    };

    fetchData();
    const interval = setInterval(fetchData, 4000);
    return () => clearInterval(interval);
  }, []);

  const cpuColor = (metrics?.cpu_percent ?? 0) > 80 ? 'text-megan-rose' : (metrics?.cpu_percent ?? 0) > 50 ? 'text-megan-amber' : 'text-megan-green';
  const memColor = (metrics?.memory_percent ?? 0) > 80 ? 'text-megan-rose' : (metrics?.memory_percent ?? 0) > 50 ? 'text-megan-amber' : 'text-megan-cyan';

  const tasks = ops?.background_tasks ?? [];
  const delegated = ops?.delegated_contacts ?? [];
  const autoHandled = ops?.auto_handled_messages ?? [];
  const thoughtStreams = ops?.background_thought_streams ?? [];

  return (
    <div className="h-full overflow-y-auto p-5 space-y-5">
      {/* System Metrics */}
      <section>
        <h3 className="text-[10px] tracking-[0.2em] text-megan-cyan mb-3">SYSTEM METRICS</h3>
        <div className="grid grid-cols-3 gap-3">
          <MetricCard label="CPU" value={`${metrics?.cpu_percent ?? 0}%`} colorClass={cpuColor} />
          <MetricCard label="MEMORY" value={`${metrics?.memory_percent ?? 0}%`} subtitle={`${metrics?.memory_used_gb ?? 0}/${metrics?.memory_total_gb ?? 0} GB`} colorClass={memColor} />
          <MetricCard label="DISK" value={`${metrics?.disk_percent ?? 0}%`} colorClass="text-megan-text-dim" />
        </div>
      </section>

      {/* WhatsApp Delegations */}
      <section>
        <h3 className="text-[10px] tracking-[0.2em] text-megan-green mb-3">WHATSAPP DELEGATIONS</h3>
        {delegated.length === 0 ? (
          <p className="text-[11px] text-megan-text-muted">No contacts are currently delegated. Megan will notify you for all incoming messages.</p>
        ) : (
          <div className="space-y-1.5">
            {delegated.map((name) => (
              <div key={name} className="flex items-center gap-2 border border-megan-border rounded px-3 py-2 bg-megan-panel/30">
                <span className="w-1.5 h-1.5 rounded-full bg-megan-green dot-pulse" />
                <span className="text-[11px] text-megan-text">{name}</span>
                <span className="text-[9px] text-megan-text-muted ml-auto tracking-wider">AUTO-HANDLE</span>
              </div>
            ))}
          </div>
        )}
      </section>

      {/* Recent Auto-Handled Messages */}
      <section>
        <h3 className="text-[10px] tracking-[0.2em] text-megan-cyan mb-3">RECENT AUTO-HANDLED</h3>
        {autoHandled.length === 0 ? (
          <p className="text-[11px] text-megan-text-muted">No messages have been auto-handled yet.</p>
        ) : (
          <div className="space-y-2">
            {autoHandled.map((msg, idx) => (
              <div key={idx} className="border border-megan-border rounded p-3 bg-megan-panel/30">
                <div className="flex items-center justify-between mb-1">
                  <span className="text-[10px] tracking-wider text-megan-text-dim">{msg.name}</span>
                  <span className="text-[9px] text-megan-text-muted">{formatTime(msg.handled_at)}</span>
                </div>
                <p className="text-[11px] text-megan-text leading-relaxed">{msg.body}</p>
              </div>
            ))}
          </div>
        )}
      </section>

      {/* Background Operations Feed (Real-time) */}
      <section>
        <h3 className="text-[10px] tracking-[0.2em] text-megan-cyan mb-3">LIVE BACKGROUND OPERATIONS</h3>
        <div className="border border-megan-border rounded bg-megan-panel/30 h-64 overflow-hidden">
          {backgroundLogicStream.length === 0 && backgroundTranscript.length === 0 ? (
            <div className="h-full flex items-center justify-center">
              <p className="text-[11px] text-megan-text-muted">No active background operations.</p>
            </div>
          ) : (
            <div className="h-full flex flex-col p-4 overflow-y-auto space-y-3">
              {backgroundTranscript.map(t => (
                <div key={t.id} className="text-[10px] text-megan-cyan border-l-2 border-megan-cyan pl-2 py-1 bg-megan-cyan/5">
                  <span className="text-megan-cyan/50 mr-2">{t.timestamp.toLocaleTimeString()}</span>
                  {t.text}
                </div>
              ))}
              {backgroundLogicStream.map(l => (
                <div key={l.id} className="text-[10px] text-megan-text-dim border-l border-megan-border/50 pl-2">
                  <span className="text-megan-text-muted/50 mr-2">{l.timestamp.toLocaleTimeString()}</span>
                  {l.type === 'thought' && <span className="italic">💭 {l.text}</span>}
                  {l.type === 'action' && <span className="text-megan-amber">⚙ {l.text}</span>}
                  {l.type === 'observation' && <span className={l.text.includes('✓') ? 'text-megan-green' : l.text.includes('✕') || l.text.includes('⚠') ? 'text-megan-rose' : ''}>{l.text}</span>}
                </div>
              ))}
            </div>
          )}
        </div>
      </section>

      {/* Background Agent Activity — Thought Streams */}
      <section>
        <h3 className="text-[10px] tracking-[0.2em] text-megan-text-muted mb-3">HISTORICAL BACKGROUND ACTIVITY</h3>
        {thoughtStreams.length === 0 ? (
          <p className="text-[11px] text-megan-text-muted">No background agent activity yet.</p>
        ) : (
          <div className="space-y-3">
            {thoughtStreams.map((stream) => (
              <div key={stream.conversation_id} className="border border-megan-border rounded p-3 bg-megan-panel/30">
                <div className="flex items-center justify-between mb-2">
                  <span className="text-[10px] tracking-wider text-megan-text-dim">{stream.name || 'Unknown'}</span>
                  <span className="text-[9px] text-megan-text-muted">{formatTime(stream.updated_at)}</span>
                </div>
                <div className="space-y-1">
                  {stream.events.map((ev, idx) => {
                    const data = ev.data as Record<string, unknown>;
                    if (ev.type === 'thread_loaded') {
                      return (
                        <div key={idx} className="text-[9px] text-megan-text-muted border-t border-megan-border pt-1 mt-1">
                          ↻ Thread loaded ({data.message_count as number} prior messages)
                        </div>
                      );
                    }
                    if (ev.type === 'message_received') {
                      return (
                        <div key={idx} className="text-[10px] text-megan-cyan">
                          → IN: {(data.body as string) || ''}
                        </div>
                      );
                    }
                    if (ev.type === 'thinking') {
                      return (
                        <div key={idx} className="text-[10px] text-megan-text-muted italic">
                          💭 {(data.text as string) || ''}
                        </div>
                      );
                    }
                    if (ev.type === 'tool_start') {
                      return (
                        <div key={idx} className="text-[10px] text-megan-warning">
                          ⚙ {String(data.tool || '').toUpperCase()}: {JSON.stringify(data.input).slice(0, 80)}
                        </div>
                      );
                    }
                    if (ev.type === 'tool_result') {
                      return (
                        <div key={idx} className={`text-[10px] ${data.success ? 'text-megan-green' : 'text-megan-error'}`}>
                          ← {String(data.tool || '')}: {(data.output as string) || ''}
                        </div>
                      );
                    }
                    if (ev.type === 'response_text') {
                      return (
                        <div key={idx} className="text-[10px] text-megan-green">
                          ← OUT: {(data.text as string) || ''}
                        </div>
                      );
                    }
                    if (ev.type === 'error') {
                      return (
                        <div key={idx} className="text-[10px] text-megan-error">
                          ⚠ ERROR: {(data.error as string) || ''}
                        </div>
                      );
                    }
                    return null;
                  })}
                </div>
              </div>
            ))}
          </div>
        )}
      </section>

      {/* Background Tasks */}
      <section>
        <h3 className="text-[10px] tracking-[0.2em] text-megan-amber mb-3">BACKGROUND TASKS</h3>
        {tasks.length === 0 ? (
          <p className="text-[11px] text-megan-text-muted">No active or recent background tasks.</p>
        ) : (
          <div className="space-y-2">
            {tasks.map((task) => (
              <div key={task.id} className="border border-megan-border rounded p-3 bg-megan-panel/30">
                <div className="flex items-center justify-between mb-1">
                  <span className="text-[10px] tracking-wider text-megan-text-dim">TASK_{task.id.toUpperCase()}</span>
                  <span className={`text-[10px] tracking-wider font-bold ${
                    task.status === 'completed' ? 'text-megan-green' :
                    task.status === 'failed' ? 'text-megan-rose' :
                    'text-megan-amber animate-pulse'
                  }`}>
                    {task.status.toUpperCase()}
                  </span>
                </div>
                <p className="text-[11px] text-megan-text leading-relaxed">{task.description.slice(0, 120)}...</p>
                <p className="text-[10px] text-megan-text-muted mt-1">Elapsed: {Math.round(task.elapsed_seconds)}s</p>
                {task.result && (
                  <p className="text-[10px] text-megan-green mt-1 leading-relaxed border-t border-megan-border pt-1">
                    {task.result.slice(0, 200)}...
                  </p>
                )}
                {task.error && (
                  <p className="text-[10px] text-megan-rose mt-1">{task.error}</p>
                )}
              </div>
            ))}
          </div>
        )}
      </section>

      {/* Safety Policies */}
      <section>
        <h3 className="text-[10px] tracking-[0.2em] text-megan-rose mb-3">SAFETY POLICIES</h3>
        <div className="space-y-1 text-[10px] text-megan-text-dim">
          <p>• <span className="text-megan-rose">BLOCK</span>: rm -rf /, DROP TABLE, curl|bash, disk format</p>
          <p>• <span className="text-megan-amber">CONFIRM</span>: sudo shutdown, sudo rm, chmod 777, TRUNCATE</p>
          <p>• <span className="text-megan-green">ALLOW</span>: All other operations</p>
        </div>
      </section>
    </div>
  );
}

function MetricCard({ label, value, subtitle, colorClass }: {
  label: string;
  value: string;
  subtitle?: string;
  colorClass: string;
}) {
  return (
    <div className="border border-megan-border rounded p-3 bg-megan-panel/30 text-center">
      <p className="text-[10px] tracking-widest text-megan-text-muted mb-1">{label}</p>
      <p className={`text-lg font-bold ${colorClass}`}>{value}</p>
      {subtitle && <p className="text-[9px] text-megan-text-muted mt-0.5">{subtitle}</p>}
    </div>
  );
}

function formatTime(iso: string): string {
  try {
    const d = new Date(iso);
    return d.toLocaleTimeString('en-US', { hour12: false, hour: '2-digit', minute: '2-digit' });
  } catch {
    return iso;
  }
}
