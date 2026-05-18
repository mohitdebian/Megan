/**
 * Transcript — clean circular chat bubbles.
 */

import { useEffect, useRef } from 'react';
import type { TranscriptEntry } from '../types';

interface Props {
  entries: TranscriptEntry[];
  currentResponse: string;
}

function formatTime(date: Date): string {
  return date.toLocaleTimeString('en-US', {
    hour12: false,
    hour: '2-digit',
    minute: '2-digit',
  });
}

function Avatar({ role }: { role: 'user' | 'megan' }) {
  if (role === 'user') {
    return (
      <div className="w-7 h-7 rounded-full bg-megan-surface border border-megan-cyan/30 flex items-center justify-center shrink-0">
        <span className="text-[9px] text-megan-cyan font-bold">OP</span>
      </div>
    );
  }
  return (
    <div className="w-7 h-7 rounded-full bg-megan-cyan/10 border border-megan-cyan/20 flex items-center justify-center shrink-0">
      <span className="text-[9px] text-megan-cyan font-bold">AI</span>
    </div>
  );
}

export function Transcript({ entries, currentResponse }: Props) {
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [entries, currentResponse]);

  if (entries.length === 0 && !currentResponse) {
    return (
      <div className="flex items-center justify-center h-full">
        <div className="text-center">
          <div className="w-16 h-16 rounded-full border border-megan-border flex items-center justify-center mx-auto mb-4">
            <span className="text-lg text-megan-text-dim">◈</span>
          </div>
          <p className="text-xs text-megan-text-dim tracking-wider">INTERFACE ACTIVE</p>
          <p className="text-[10px] text-megan-text-muted mt-1 tracking-wider">AWAITING INPUT</p>
        </div>
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-5 overflow-y-auto h-full px-6 py-5">
      {entries.map((entry) => {
        const isUser = entry.role === 'user';
        return (
          <div key={entry.id} className={`flex gap-3 animate-fade-in ${isUser ? 'flex-row-reverse' : ''}`}>
            <Avatar role={entry.role} />
            <div className={`max-w-[75%] ${isUser ? 'items-end' : 'items-start'} flex flex-col gap-1`}>
              <div className="flex items-center gap-2">
                <span className={`text-[9px] tracking-wider font-bold ${isUser ? 'text-megan-cyan' : 'text-megan-text-dim'}`}>
                  {isUser ? 'YOU' : 'MEGAN'}
                </span>
                <span className="text-[9px] text-megan-text-muted">{formatTime(entry.timestamp)}</span>
              </div>
              <div
                className={`px-4 py-2.5 rounded-2xl text-[12px] leading-relaxed whitespace-pre-wrap ${
                  isUser
                    ? 'bg-megan-cyan/8 border border-megan-cyan/15 text-megan-text'
                    : 'bg-megan-surface border border-megan-border text-megan-text'
                }`}
              >
                {entry.text}
              </div>
            </div>
          </div>
        );
      })}

      {/* Streaming response */}
      {currentResponse && (
        <div className="flex gap-3 animate-fade-in">
          <Avatar role="megan" />
          <div className="max-w-[75%] flex flex-col gap-1">
            <div className="flex items-center gap-2">
              <span className="text-[9px] tracking-wider font-bold text-megan-text-dim">MEGAN</span>
              <span className="text-[9px] text-megan-text-muted">{formatTime(new Date())}</span>
              <span className="w-1.5 h-1.5 rounded-full bg-megan-cyan animate-pulse" />
            </div>
            <div className="px-4 py-2.5 rounded-2xl bg-megan-surface border border-megan-border text-[12px] leading-relaxed">
              <span className="cursor-blink">{currentResponse}</span>
            </div>
          </div>
        </div>
      )}

      <div ref={bottomRef} />
    </div>
  );
}
