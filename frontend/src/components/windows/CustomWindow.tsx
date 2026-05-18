import React from 'react';

export function CustomWindow({ content }: { content?: string }) {
  if (!content) {
    return <div style={{ padding: '20px', color: 'var(--text-dim)' }}>Empty Custom Window</div>;
  }
  
  return (
    <div 
      style={{ padding: '15px', color: 'var(--text-main)', height: '100%', overflowY: 'auto' }}
      dangerouslySetInnerHTML={{ __html: content }}
    />
  );
}
