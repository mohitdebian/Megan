import React from 'react';
import { Window } from './Window';

export interface AppWindow {
  id: string;
  type: string;
  title: string;
  icon: string;
  width: number;
  height: number;
  query?: string;
  content?: string;
  items?: any[];
  position: string;
  x: number;
  y: number;
  zIndex: number;
}

interface DesktopProps {
  windows: AppWindow[];
  onFocusWindow: (id: string) => void;
  onCloseWindow: (id: string) => void;
}

export function Desktop({ windows, onFocusWindow, onCloseWindow }: DesktopProps) {
  return (
    <div className="absolute inset-0 overflow-hidden bg-megan-bg desktop-bg" style={{ zIndex: 1 }}>
      <div className="scanlines" />
      {windows.map((win) => (
        <Window
          key={win.id}
          window={win}
          onFocus={() => onFocusWindow(win.id)}
          onClose={() => onCloseWindow(win.id)}
        />
      ))}
      {windows.length === 0 && (
        <div className="absolute inset-0 flex items-center justify-center pointer-events-none opacity-50">
          <div className="text-center">
            <h1 className="text-4xl text-megan-cyan font-bold tracking-[0.3em] mb-2 text-glow">MEGAN_OS</h1>
            <p className="text-sm tracking-widest text-megan-text-muted">AWAITING NEURAL COMMANDS</p>
          </div>
        </div>
      )}
    </div>
  );
}
