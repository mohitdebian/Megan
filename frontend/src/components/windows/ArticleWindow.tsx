import React from 'react';
import { FileText } from 'lucide-react';

export function ArticleWindow({ query }: { query?: string }) {
  return (
    <div style={{ padding: '20px', color: 'var(--text-main)', lineHeight: 1.6 }}>
      <h2 style={{ fontSize: '18px', color: 'var(--color-cyan)', marginBottom: '10px', display: 'flex', alignItems: 'center', gap: '8px' }}>
        <FileText size={18} /> {query || "Wikipedia Article"}
      </h2>
      
      <p style={{ fontSize: '12px', marginBottom: '10px' }}>
        <strong>{query}</strong> is a highly discussed topic in modern computing and cybernetics. Recent advancements have accelerated its adoption across multiple sectors.
      </p>
      
      <p style={{ fontSize: '12px', marginBottom: '10px' }}>
        Experts suggest that the integration of {query} will fundamentally alter the paradigm of human-computer interaction over the next decade.
      </p>

      <div style={{ marginTop: '20px', paddingTop: '10px', borderTop: '1px dashed var(--panel-border)', fontSize: '10px', color: 'var(--text-dim)' }}>
        Source: Encrypted Archive 7A // Last updated: 2026
      </div>
    </div>
  );
}
