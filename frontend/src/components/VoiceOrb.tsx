/**
 * VoiceOrb — holographic circular state indicator with spinning ring.
 */

import type { MeganState } from '../types';

interface Props {
  state: MeganState;
  onClick: () => void;
  isRecording: boolean;
}

const stateColors: Record<MeganState, string> = {
  idle: '#22d3ee',
  listening: '#34d399',
  thinking: '#f59e0b',
  speaking: '#22d3ee',
  tool_executing: '#f59e0b',
};

const stateLabels: Record<MeganState, string> = {
  idle: 'TAP TO SPEAK',
  listening: 'LISTENING',
  thinking: 'THINKING',
  speaking: 'SPEAKING',
  tool_executing: 'WORKING',
};

export function VoiceOrb({ state, onClick, isRecording }: Props) {
  const color = stateColors[state];
  const label = stateLabels[state];
  const isActive = state !== 'idle';

  return (
    <div className="flex flex-col items-center gap-4 select-none">
      <button
        id="voice-orb"
        onClick={onClick}
        className="relative w-20 h-20 flex items-center justify-center group"
      >
        {/* Outer spinning ring (holographic) */}
        <div
          className={`absolute inset-0 rounded-full border ${isActive ? 'border-spin' : ''}`}
          style={{
            borderColor: `${color}40`,
            borderWidth: '1px',
            borderStyle: isActive ? 'dashed' : 'solid',
          }}
        />
        {/* Second ring, offset */}
        <div
          className={`absolute inset-1 rounded-full border ${isActive ? 'animate-spin-slow' : ''}`}
          style={{
            borderColor: `${color}20`,
            borderWidth: '1px',
            borderStyle: isActive ? 'dotted' : 'solid',
          }}
        />
        {/* Inner solid orb */}
        <div
          className={`w-12 h-12 rounded-full transition-all duration-500 ${isActive ? 'animate-orb-breathe' : ''} group-hover:scale-110 group-active:scale-95`}
          style={{
            background: color,
            boxShadow: `0 0 0 4px ${color}15, 0 0 20px ${color}20, 0 0 40px ${color}10`,
          }}
        />
        {/* Center icon */}
        <div className="absolute inset-0 flex items-center justify-center">
          {state === 'idle' && (
            <svg className="w-5 h-5 text-megan-bg" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M12 18.75a6 6 0 006-6v-1.5m-6 7.5a6 6 0 01-6-6v-1.5m6 7.5v3.75m-3.75 0h7.5M12 15.75a3 3 0 01-3-3V4.5a3 3 0 116 0v8.25a3 3 0 01-3 3z" />
            </svg>
          )}
          {isRecording && (
            <div className="w-3.5 h-3.5 rounded-sm bg-megan-bg" />
          )}
          {state === 'thinking' && (
            <div className="w-2 h-2 rounded-full bg-megan-bg animate-pulse" />
          )}
          {state === 'speaking' && (
            <div className="w-2 h-2 rounded-full bg-megan-bg" />
          )}
          {state === 'tool_executing' && (
            <div className="w-3 h-3 border-2 border-megan-bg border-t-transparent rounded-full animate-spin" />
          )}
        </div>
      </button>
      <span className="text-[10px] tracking-[0.2em] text-megan-text-dim font-mono">
        {label}
      </span>
    </div>
  );
}
