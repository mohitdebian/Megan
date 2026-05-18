/**
 * ToolFeed — clean tool execution cards.
 */

import { useEffect, useRef } from 'react';
import type { ToolExecution } from '../types';

interface Props {
  tools: ToolExecution[];
}

const statusStyles: Record<string, { icon: string; color: string }> = {
  running: { icon: '↻', color: 'text-megan-purple' },
  done: { icon: '✓', color: 'text-megan-success' },
  error: { icon: '✕', color: 'text-megan-error' },
};

export function ToolFeed({ tools }: Props) {
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [tools]);

  if (tools.length === 0) {
    return (
      <div className="flex items-center justify-center h-full">
        <p className="text-xs text-megan-text-dim/40">No tools used</p>
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-1.5 overflow-y-auto h-full px-3 py-2">
      {tools.map((tool) => {
        const status = statusStyles[tool.status] || statusStyles.running;
        return (
          <div
            key={tool.id}
            className="animate-slide-up bg-megan-panel rounded-lg px-3 py-2"
          >
            <div className="flex items-center gap-2">
              <span className={`text-xs ${status.color} ${tool.status === 'running' ? 'animate-spin' : ''}`}>
                {status.icon}
              </span>
              <span className="text-xs font-medium text-megan-text">
                {tool.tool}
              </span>
            </div>

            {tool.output && (
              <p className="text-[10px] text-megan-text-dim mt-1 truncate">
                {tool.output.slice(0, 120)}
              </p>
            )}
          </div>
        );
      })}
      <div ref={bottomRef} />
    </div>
  );
}
