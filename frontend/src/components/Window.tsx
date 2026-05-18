import React, { useState } from 'react';
import { motion } from 'framer-motion';
import { X, Minus, Square } from 'lucide-react';
import { AppWindow } from './Desktop';
import { NewsWindow, YoutubeWindow, WeatherWindow, ArticleWindow, ChatWindow, CustomWindow } from './windows';

interface Props {
  window: AppWindow;
  onFocus: () => void;
  onClose: () => void;
}

export function Window({ window: win, onFocus, onClose }: Props) {
  const [size, setSize] = useState({ width: win.width, height: win.height });
  const [isMinimized, setIsMinimized] = useState(false);

  const renderContent = () => {
    switch (win.type) {
      case 'news': return <NewsWindow query={win.query} items={win.items} />;
      case 'youtube': return <YoutubeWindow query={win.query} items={win.items} />;
      case 'weather': return <WeatherWindow query={win.query} items={win.items} />;
      case 'article': return <ArticleWindow query={win.query} />;
      case 'chat': return <ChatWindow content={win.content} />;
      case 'custom': return <CustomWindow content={win.content} />;
      default: return <div className="p-5 text-megan-text-dim">Unknown window type: {win.type}</div>;
    }
  };

  return (
    <motion.div
      drag
      dragMomentum={false}
      initial={{ x: win.x, y: win.y, scale: 0.8, opacity: 0 }}
      animate={{ scale: 1, opacity: 1 }}
      onPointerDown={onFocus}
      style={{
        position: 'absolute',
        width: size.width,
        height: isMinimized ? 40 : size.height,
        zIndex: win.zIndex,
        display: 'flex',
        flexDirection: 'column',
        borderRadius: '8px',
        overflow: 'hidden'
      }}
      className="glass-panel"
    >
      {/* Header Bar */}
      <div 
        className="window-header bg-megan-bg/50 border-b border-megan-border flex items-center px-3 cursor-grab select-none"
        style={{ height: '40px' }}
      >
        <span className="mr-2 text-sm">{win.icon || '💻'}</span>
        <span className="text-xs font-bold text-megan-cyan flex-1 overflow-hidden text-ellipsis whitespace-nowrap">
          {win.title.toUpperCase()}
        </span>
        
        <div className="flex gap-2">
          <button onClick={() => setIsMinimized(!isMinimized)} className="text-megan-text-dim hover:text-megan-text"><Minus size={14}/></button>
          <button className="text-megan-text-dim hover:text-megan-text"><Square size={12}/></button>
          <button onClick={onClose} className="text-megan-rose/70 hover:text-megan-rose"><X size={14}/></button>
        </div>
      </div>

      {/* Content */}
      {!isMinimized && (
        <div className="flex-1 overflow-auto relative bg-megan-surface/80">
          {renderContent()}
          
          {/* Resize Handle */}
          <div 
            onPointerDown={(e) => {
              e.stopPropagation();
              const startX = e.clientX;
              const startY = e.clientY;
              const startWidth = size.width;
              const startHeight = size.height;
              
              const onMove = (me: PointerEvent) => {
                setSize({
                  width: Math.max(200, startWidth + (me.clientX - startX)),
                  height: Math.max(150, startHeight + (me.clientY - startY))
                });
              };
              
              const onUp = () => {
                document.removeEventListener('pointermove', onMove);
                document.removeEventListener('pointerup', onUp);
              };
              
              document.addEventListener('pointermove', onMove);
              document.addEventListener('pointerup', onUp);
            }}
            style={{
              position: 'absolute',
              bottom: 0,
              right: 0,
              width: '15px',
              height: '15px',
              cursor: 'se-resize',
              background: 'linear-gradient(135deg, transparent 50%, var(--color-cyan-dim) 50%)'
            }}
          />
        </div>
      )}
    </motion.div>
  );
}
