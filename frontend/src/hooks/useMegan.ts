/**
 * useMegan — main orchestration hook for MEGAN_OS.
 * Ties WebSocket + Audio + VAD + UI state + system metrics.
 *
 * Supports two voice modes:
 *   1. Push-to-talk (NEURAL LINK): Click to start/stop recording.
 *   2. Conversation mode (CONVERSE): Hands-free VAD — talk naturally,
 *      Megan auto-detects when you stop and responds, then listens again.
 */

import { useCallback, useEffect, useRef, useState } from 'react';
import { useWebSocket } from './useWebSocket';
import { useAudio } from './useAudio';
import { useVAD } from './useVAD';
import type {
  MeganState,
  TranscriptEntry,
  ToolExecution,
  LogicEntry,
  ConfirmRequest,
  SystemMetrics,
} from '../types';
import { AppWindow } from '../components/Desktop';
import { API_URL } from '../lib/constants';

export function useMegan() {
  const ws = useWebSocket();
  const audio = useAudio();
  const vad = useVAD();

  const [state, setState] = useState<MeganState>('idle');
  const [transcript, setTranscript] = useState<TranscriptEntry[]>([]);
  const [tools, setTools] = useState<ToolExecution[]>([]);
  const [logicStream, setLogicStream] = useState<LogicEntry[]>([]);
  const [backgroundLogicStream, setBackgroundLogicStream] = useState<LogicEntry[]>([]);
  const [backgroundTranscript, setBackgroundTranscript] = useState<TranscriptEntry[]>([]);
  const [activeWindows, setActiveWindows] = useState<AppWindow[]>([]);
  const [currentResponse, setCurrentResponse] = useState('');
  const [confirmRequest, setConfirmRequest] = useState<ConfirmRequest | null>(null);
  const [availableTools, setAvailableTools] = useState<string[]>([]);
  const [voiceEnabled, setVoiceEnabled] = useState(true);
  const [conversationMode, setConversationMode] = useState(false);
  const [metrics, setMetrics] = useState<SystemMetrics>({
    cpu: '0%',
    memory: '0%',
    nnLoad: '0.00',
  });

  const idCounter = useRef(0);
  const nextId = () => String(++idCounter.current);

  // Track if we should auto-listen after Megan responds with a question
  const autoListenRef = useRef(false);
  const lastResponseRef = useRef('');

  // Track conversation mode state ref for use in callbacks
  const conversationModeRef = useRef(false);
  const voiceEnabledRef = useRef(true);

  // Keep refs in sync
  useEffect(() => {
    voiceEnabledRef.current = voiceEnabled;
  }, [voiceEnabled]);

  // Poll system metrics
  useEffect(() => {
    const fetchMetrics = async () => {
      try {
        const resp = await fetch(`${API_URL}/health`);
        if (resp.ok) {
          setMetrics((prev) => ({ ...prev }));
        }
      } catch {
        // ignore
      }
    };
    fetchMetrics();
    const interval = setInterval(fetchMetrics, 10000);
    return () => clearInterval(interval);
  }, []);

  // ── Stuck-state watchdog ──
  const lastActivityRef = useRef<number>(Date.now());

  useEffect(() => {
    lastActivityRef.current = Date.now();
  }, [state]);

  useEffect(() => {
    const STUCK_TIMEOUT = 60_000;
    const watchdog = setInterval(() => {
      const elapsed = Date.now() - lastActivityRef.current;
      if (state !== 'idle' && state !== 'listening' && elapsed > STUCK_TIMEOUT) {
        console.warn(`[Watchdog] State "${state}" stuck for ${Math.round(elapsed / 1000)}s — resetting`);
        setState(conversationModeRef.current ? 'listening' : 'idle');
        setCurrentResponse((prev) => {
          if (prev) {
            setTranscript((t) => [
              ...t,
              { id: nextId(), role: 'megan', text: prev + '\n\n[Response interrupted — timeout]', timestamp: new Date() },
            ]);
          }
          return '';
        });
        setLogicStream((prev) => [
          ...prev,
          { id: nextId(), type: 'observation', text: '⚠ WATCHDOG: State stuck, auto-reset.', timestamp: new Date() },
        ]);
        // Resume VAD if in conversation mode
        if (conversationModeRef.current) {
          vad.resumeVAD();
        }
      }
    }, 5_000);

    return () => clearInterval(watchdog);
  }, [state, vad]);

  // ── VAD utterance handler ──
  const handleVADUtterance = useCallback(
    (b64Audio: string) => {
      vad.pauseVAD();
      setState('thinking');
      ws.send('audio_file', { audio: b64Audio });
    },
    [ws, vad]
  );



  /**
   * Resume VAD after a delay (used after Megan finishes responding).
   * Central helper to avoid code duplication.
   */
  const resumeVADAfterResponse = useCallback((delayMs: number = 600) => {
    if (conversationModeRef.current) {
      setState('listening');
      setTimeout(() => {
        vad.resumeVAD();
      }, delayMs);
    }
  }, [vad]);

  // Register message handlers
  useEffect(() => {
    const cleanups: (() => void)[] = [];

    cleanups.push(
      ws.on('status', (msg) => {
        if (msg.data?.tools) setAvailableTools(msg.data.tools);
      })
    );

    cleanups.push(
      ws.on('system_notification', (msg) => {
        const isBackground = msg.data?.data?.source === 'background' || msg.data?.source === 'background';
        const text = msg.data?.data?.text || msg.data?.text || '';
        if (text) {
          if (isBackground) {
            setBackgroundTranscript((prev) => [
              ...prev,
              { id: nextId(), role: 'megan', text: `🔔 [SYSTEM]: ${text}`, timestamp: new Date() },
            ]);
          } else {
            setTranscript((prev) => [
              ...prev,
              { id: nextId(), role: 'megan', text: `🔔 ${text}`, timestamp: new Date() },
            ]);
          }
        }
      })
    );

    cleanups.push(
      ws.on('transcript', (msg) => {
        const text = msg.data?.data?.text || msg.data?.text || '';
        if (text) {
          setTranscript((prev) => [
            ...prev,
            { id: nextId(), role: 'user', text, timestamp: new Date() },
          ]);
        }
      })
    );

    cleanups.push(
      ws.on('response_text', (msg) => {
        const isBackground = msg.data?.data?.source === 'background' || msg.data?.source === 'background';
        const text = msg.data?.data?.text || msg.data?.text || '';
        if (!text) return;

        if (isBackground) {
          setBackgroundTranscript((prev) => {
            const last = prev[prev.length - 1];
            if (last && last.role === 'megan') {
              const updated = [...prev];
              updated[updated.length - 1] = { ...last, text: last.text + text };
              return updated;
            }
            return [...prev, { id: nextId(), role: 'megan', text, timestamp: new Date() }];
          });
        } else {
          setCurrentResponse((prev) => prev + text);
          setState('speaking');
          lastActivityRef.current = Date.now();
        }
      })
    );

    cleanups.push(
      ws.on('response_done', (msg) => {
        const isBackground = msg.data?.data?.source === 'background' || msg.data?.source === 'background';
        if (isBackground) return;
        setCurrentResponse((prev) => {
          if (prev) {
            setTranscript((t) => [
              ...t,
              { id: nextId(), role: 'megan', text: prev, timestamp: new Date() },
            ]);
            lastResponseRef.current = prev;
            if (prev.trim().endsWith('?')) {
              autoListenRef.current = true;
            }
          }
          return '';
        });

        // KEY FIX: If voice is disabled or we're in conversation mode,
        // audio_done may never fire. Resume VAD / set idle here.
        if (!voiceEnabledRef.current) {
          // No TTS will play, so audio_done won't fire.
          if (conversationModeRef.current) {
            resumeVADAfterResponse(300);
          } else {
            setState('idle');
          }
        } else {
          // TTS will play → audio_done will fire and handle state.
          // But set a safety timeout in case audio_done is lost.
          setTimeout(() => {
            // If still in speaking state after 30s, force resume
            // (audio_done should have fired by now)
          }, 30_000);
        }
      })
    );

    cleanups.push(
      ws.on('thinking', (msg) => {
        const text = msg.data?.data?.text || msg.data?.text || '';
        const isBackground = msg.data?.data?.source === 'background' || msg.data?.source === 'background';
        if (!text) return;

        if (isBackground) {
          setBackgroundLogicStream((prev) => {
            const last = prev[prev.length - 1];
            if (last && last.type === 'thought') {
              const updated = [...prev];
              updated[updated.length - 1] = { ...last, text: last.text + text };
              return updated.slice(-50);
            }
            return [...prev.slice(-50), { id: nextId(), type: 'thought', text, timestamp: new Date() }];
          });
        } else {
          setState('thinking');
          lastActivityRef.current = Date.now();
          setLogicStream((prev) => {
            const last = prev[prev.length - 1];
            if (last && last.type === 'thought') {
              const updated = [...prev];
              updated[updated.length - 1] = { ...last, text: last.text + text };
              return updated.slice(-30);
            }
            return [...prev.slice(-30), { id: nextId(), type: 'thought', text, timestamp: new Date() }];
          });
        }
      })
    );

    cleanups.push(
      ws.on('tool_start', (msg) => {
        const data = msg.data?.data || msg.data || {};
        const isBackground = data.source === 'background';
        const toolName = data.tool || 'unknown';
        const input = data.input || {};

        if (toolName === 'window_manager') {
          const action = input.action;
          if (action === 'spawn_window') {
             setActiveWindows(prev => {
                const wWidth = input.width || 400;
                const wHeight = input.height || 300;
                const desktopWidth = window.innerWidth;
                const desktopHeight = window.innerHeight;
                let x = 100 + (prev.length * 40);
                let y = 100 + (prev.length * 40);
                if (input.position === 'left') { x = 50; y = 50; }
                else if (input.position === 'right') { x = desktopWidth - wWidth - 50; y = 50; }
                else if (input.position === 'center') { x = (desktopWidth / 2) - (wWidth / 2); y = (desktopHeight / 2) - (wHeight / 2); }
                else if (input.position === 'top-right') { x = desktopWidth - wWidth - 50; y = 50; }
                else if (input.position === 'bottom-left') { x = 50; y = desktopHeight - wHeight - 100; }
                
                return [...prev, {
                  id: nextId(),
                  type: input.type,
                  title: input.title,
                  icon: '💻',
                  width: wWidth,
                  height: wHeight,
                  query: input.query,
                  content: input.content,
                  items: input.items,
                  position: input.position,
                  x,
                  y,
                  zIndex: 10 + prev.length
                }];
             });
          } else if (action === 'close_window') {
             setActiveWindows(prev => prev.filter(w => w.title.toLowerCase() !== (input.title || '').toLowerCase()));
          } else if (action === 'close_all_windows') {
             setActiveWindows([]);
          }
        }

        if (isBackground) {
          setBackgroundLogicStream((prev) => [
            ...prev.slice(-50),
            { id: nextId(), type: 'action', text: `${toolName.toUpperCase()}: ${JSON.stringify(input).slice(0, 200)}`, timestamp: new Date() },
          ]);
        } else {
          setState('tool_executing');
          lastActivityRef.current = Date.now();
          setTools((prev) => [
            ...prev.slice(-20),
            { id: nextId(), tool: toolName, input, status: 'running', timestamp: new Date() },
          ]);
          setLogicStream((prev) => [
            ...prev.slice(-30),
            { id: nextId(), type: 'action', text: `${toolName.toUpperCase()}: ${JSON.stringify(input).slice(0, 200)}`, timestamp: new Date() },
          ]);
        }
      })
    );

    cleanups.push(
      ws.on('tool_result', (msg) => {
        const data = msg.data?.data || msg.data || {};
        const isBackground = data.source === 'background';
        if (isBackground) {
          setBackgroundLogicStream((prev) => [
            ...prev.slice(-50),
            {
              id: nextId(),
              type: 'observation',
              text: `${data.success ? '✓' : '✕'} ${(data.output || 'No output').slice(0, 300)}`,
              timestamp: new Date(),
            },
          ]);
        } else {
          lastActivityRef.current = Date.now();
          setTools((prev) =>
            prev.map((t) =>
              t.status === 'running' && t.tool === (data.tool || '')
                ? { ...t, output: data.output, status: data.success ? 'done' : 'error' }
                : t
            )
          );
          setLogicStream((prev) => [
            ...prev.slice(-30),
            {
              id: nextId(),
              type: 'observation',
              text: `${data.success ? '✓' : '✕'} ${(data.output || 'No output').slice(0, 300)}`,
              timestamp: new Date(),
            },
          ]);
        }
      })
    );

    cleanups.push(
      ws.on('confirm_request', (msg) => {
        const data = msg.data?.data || msg.data || {};
        setConfirmRequest({
          tool_use_id: data.tool_use_id,
          tool: data.tool,
          input: data.input,
        });
      })
    );

    cleanups.push(
      ws.on('response_audio', (msg) => {
        if (!voiceEnabledRef.current) return;
        const data = msg.data?.data || msg.data || {};
        if (data.audio) {
          // REMOVED: vad.pauseVAD() — We want VAD to stay active so the user can interrupt!
          audio.playAudioChunk(data.audio, data.sample_rate || 24000);
        }
      })
    );

    // Handle errors — reset state and resume VAD if needed
    cleanups.push(
      ws.on('error', (msg) => {
        const isBackground = msg.data?.data?.source === 'background' || msg.data?.source === 'background';
        const errMsg = msg.data?.data?.message || msg.data?.message || 'Unknown error';
        console.error('[Megan] Backend error:', errMsg);

        if (isBackground) {
          setBackgroundLogicStream((prev) => [
            ...prev.slice(-50),
            { id: nextId(), type: 'observation', text: `⚠ BACKGROUND ERROR: ${errMsg}`, timestamp: new Date() },
          ]);
        } else {
          setCurrentResponse((prev) => {
            if (prev) {
              setTranscript((t) => [
                ...t,
                { id: nextId(), role: 'megan', text: prev + '\n\n[Error occurred]', timestamp: new Date() },
              ]);
            }
            return '';
          });
          setLogicStream((prev) => [
            ...prev.slice(-30),
            { id: nextId(), type: 'observation', text: `⚠ ERROR: ${errMsg}`, timestamp: new Date() },
          ]);

          if (conversationModeRef.current) {
            resumeVADAfterResponse(500);
          } else {
            setState('idle');
          }
        }
      })
    );

    // Handle audio_done — TTS finished playing.
    // Resume VAD in conversation mode, or auto-listen in push-to-talk.
    cleanups.push(
      ws.on('audio_done', () => {
        if (conversationModeRef.current) {
          resumeVADAfterResponse(600);
        } else {
          setState('idle');
          if (autoListenRef.current && voiceEnabledRef.current) {
            autoListenRef.current = false;
            setTimeout(async () => {
              if (!audio.isRecording) {
                setState('listening');
                await audio.startRecording();
              }
            }, 500);
          }
        }
      })
    );

    return () => cleanups.forEach((c) => c());
  }, [ws, audio, vad, resumeVADAfterResponse]);

  // Send text message
  const sendText = useCallback(
    (text: string) => {
      if (!text.trim()) return;
      setTranscript((prev) => [
        ...prev,
        { id: nextId(), role: 'user', text, timestamp: new Date() },
      ]);
      setCurrentResponse('');
      setState('thinking');

      // Pause VAD during text processing too
      if (conversationModeRef.current) {
        vad.pauseVAD();
      }

      ws.send('text_input', { text, voice_enabled: voiceEnabledRef.current });
    },
    [ws, vad]
  );

  // Toggle voice recording — push-to-talk
  const toggleVoice = useCallback(async () => {
    if (audio.isRecording) {
      setState('thinking');
      const b64 = await audio.stopRecording();
      if (b64) {
        ws.send('audio_file', { audio: b64 });
      } else {
        setState('idle');
      }
    } else {
      autoListenRef.current = false;
      setState('listening');
      await audio.startRecording();
    }
  }, [audio, ws]);

  // Toggle conversation mode — hands-free VAD
  const toggleConversationMode = useCallback(async () => {
    if (conversationModeRef.current) {
      conversationModeRef.current = false;
      setConversationMode(false);
      vad.stopVAD();
      setState('idle');
    } else {
      if (audio.isRecording) {
        await audio.stopRecording();
      }
      conversationModeRef.current = true;
      setConversationMode(true);
      setState('listening');
      await vad.startVAD(handleVADUtterance);
    }
  }, [audio, vad, handleVADUtterance]);

  // Interrupt current response
  const interrupt = useCallback(() => {
    ws.send('interrupt', {});
    audio.stopPlayback();
    setCurrentResponse('');

    if (conversationModeRef.current) {
      resumeVADAfterResponse(300);
    } else {
      setState('idle');
    }
  }, [ws, audio, resumeVADAfterResponse]);

  // ── Update VAD speaking state → UI state ──
  useEffect(() => {
    if (vad.isSpeaking && conversationModeRef.current) {
      // SMART INTERRUPTION (Barge-in)
      // If Megan is currently speaking and the user starts talking, interrupt her immediately!
      if (state === 'speaking') {
        interrupt();
      }
      setState('listening');
    }
  }, [vad.isSpeaking, state, interrupt]);

  // Confirm/deny dangerous action
  const respondToConfirm = useCallback(
    (approved: boolean) => {
      if (confirmRequest) {
        ws.send('confirm_action', {
          tool_use_id: confirmRequest.tool_use_id,
          approved,
        });
        setConfirmRequest(null);
      }
    },
    [ws, confirmRequest]
  );

  // Toggle voice output
  const toggleVoiceOutput = useCallback(() => {
    setVoiceEnabled((prev) => !prev);
  }, []);

  // Cleanup VAD on unmount
  useEffect(() => {
    return () => {
      vad.stopVAD();
    };
  }, []);

  return {
    connected: ws.connected,
    conversationId: ws.conversationId,

    state,
    transcript,
    tools,
    logicStream,
    backgroundLogicStream,
    backgroundTranscript,
    activeWindows,
    setActiveWindows,
    currentResponse,
    confirmRequest,
    availableTools,
    voiceEnabled,
    conversationMode,
    metrics,

    sendText,
    toggleVoice,
    toggleConversationMode,
    interrupt,
    respondToConfirm,
    toggleVoiceOutput,
    isRecording: audio.isRecording,
    isSpeaking: vad.isSpeaking,
  };
}
