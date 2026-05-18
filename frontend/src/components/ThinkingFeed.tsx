/**
 * ThinkingFeed — shows reasoning in a clean, minimal style.
 */

import { useEffect, useRef } from 'react';
import type { ThinkingEntry } from '../types';

interface Props {
  entries: ThinkingEntry[];
}

export function ThinkingFeed({ entries }: Props) {
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [entries]);

  if (entries.length === 0) {
    return (
      <div className="flex items-center justify-center h-full">
        <p className="text-xs text-megan-text-dim/40">No activity yet</p>
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-2 overflow-y-auto h-full px-4 py-2">
      {entries.map((entry) => (
        <div key={entry.id} className="animate-fade-in">
          <p className="text-xs text-megan-text-dim leading-relaxed">
            {entry.text.slice(0, 300)}
            {entry.text.length > 300 && '...'}
          </p>
        </div>
      ))}
      <div ref={bottomRef} />
    </div>
  );
}
