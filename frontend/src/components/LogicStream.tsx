/**
 * LogicStream — personal task thought trace.
 */

import { useEffect, useRef } from 'react';
import type { LogicEntry } from '../types';

interface Props {
  entries: LogicEntry[];
}

const TYPE_CONFIG: Record<string, { label: string; color: string; border: string }> = {
  thought: { label: 'THINK', color: 'text-megan-cyan', border: 'border-megan-cyan/20' },
  action: { label: 'ACTION', color: 'text-megan-amber', border: 'border-megan-amber/20' },
  observation: { label: 'RESULT', color: 'text-megan-green', border: 'border-megan-green/20' },
};

function formatTime(date: Date): string {
  return date.toLocaleTimeString('en-US', { hour12: false, hour: '2-digit', minute: '2-digit', second: '2-digit' });
}

export function LogicStream({ entries }: Props) {
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [entries]);

  if (entries.length === 0) {
    return (
      <div className="flex items-center justify-center h-full">
        <p className="text-[10px] text-megan-text-muted tracking-wider">NO PERSONAL ACTIVITY</p>
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-0 overflow-y-auto h-full">
      {entries.map((entry) => {
        const config = TYPE_CONFIG[entry.type] || TYPE_CONFIG.thought;
        return (
          <div
            key={entry.id}
            className="px-3 py-2 border-b border-megan-border/30 animate-slide-up hover:bg-megan-panel/20 transition-colors"
          >
            <div className="flex items-center justify-between mb-1">
              <span className={`text-[9px] tracking-widest font-bold ${config.color}`}>{config.label}</span>
              <span className="text-[8px] text-megan-text-muted tabular-nums">{formatTime(entry.timestamp)}</span>
            </div>
            <p className={`text-[10px] leading-relaxed text-megan-text-dim pl-2 border-l ${config.border}`}>
              {entry.text.slice(0, 200)}{entry.text.length > 200 && '...'}
            </p>
          </div>
        );
      })}
      <div ref={bottomRef} />
    </div>
  );
}
