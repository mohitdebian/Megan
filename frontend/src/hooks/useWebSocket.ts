/**
 * useWebSocket — WebSocket connection with auto-reconnect and message routing.
 */

import { useCallback, useEffect, useRef, useState } from 'react';
import { WS_URL } from '../lib/constants';
import type { WSMessage } from '../types';

type MessageHandler = (msg: WSMessage) => void;

export function useWebSocket() {
  const wsRef = useRef<WebSocket | null>(null);
  const handlersRef = useRef<Map<string, MessageHandler[]>>(new Map());
  const [connected, setConnected] = useState(false);
  const [conversationId, setConversationId] = useState<string>('');
  const reconnectRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const connect = useCallback(() => {
    if (wsRef.current?.readyState === WebSocket.OPEN) return;

    const ws = new WebSocket(WS_URL);

    ws.onopen = () => {
      setConnected(true);
      console.log('[WS] Connected');
    };

    ws.onmessage = (event) => {
      try {
        const msg: WSMessage = JSON.parse(event.data);

        // Handle status messages
        if (msg.type === 'status' && msg.data?.conversation_id) {
          setConversationId(msg.data.conversation_id);
        }

        // Route to registered handlers
        const handlers = handlersRef.current.get(msg.type) || [];
        handlers.forEach((h) => h(msg));

        // Also notify global handlers
        const globalHandlers = handlersRef.current.get('*') || [];
        globalHandlers.forEach((h) => h(msg));
      } catch (e) {
        console.error('[WS] Parse error:', e);
      }
    };

    ws.onclose = () => {
      setConnected(false);
      console.log('[WS] Disconnected, reconnecting...');
      reconnectRef.current = setTimeout(connect, 2000);
    };

    ws.onerror = (e) => {
      console.error('[WS] Error:', e);
    };

    wsRef.current = ws;
  }, []);

  useEffect(() => {
    connect();
    return () => {
      if (reconnectRef.current) {
        clearTimeout(reconnectRef.current);
      }
      wsRef.current?.close();
    };
  }, [connect]);

  const send = useCallback((type: string, data: Record<string, any> = {}) => {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify({ type, data }));
    }
  }, []);

  const on = useCallback((type: string, handler: MessageHandler) => {
    if (!handlersRef.current.has(type)) {
      handlersRef.current.set(type, []);
    }
    handlersRef.current.get(type)!.push(handler);

    // Return cleanup function
    return () => {
      const handlers = handlersRef.current.get(type) || [];
      handlersRef.current.set(type, handlers.filter((h) => h !== handler));
    };
  }, []);

  return { connected, conversationId, send, on };
}
