import React from 'react';
import { MessageSquare } from 'lucide-react';

export function ChatWindow({ content }: { content?: string }) {
  return (
    <div style={{ padding: '15px', color: 'var(--text-main)', height: '100%', display: 'flex', flexDirection: 'column' }}>
      <h3 style={{ fontSize: '12px', marginBottom: '15px', color: 'var(--color-purple)', display: 'flex', alignItems: 'center', gap: '8px' }}>
        <MessageSquare size={14} /> MEGAN RESPONSE
      </h3>
      
      <div style={{ 
        flex: 1, 
        background: 'rgba(0,0,0,0.4)', 
        border: '1px solid var(--panel-border)', 
        borderRadius: '6px', 
        padding: '15px',
        fontSize: '13px',
        lineHeight: 1.5,
        overflowY: 'auto'
      }}>
        {content || "Analyzing query..."}
      </div>
    </div>
  );
}
