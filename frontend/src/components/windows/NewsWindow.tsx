import React from 'react';
import { Newspaper } from 'lucide-react';

export function NewsWindow({ query, items }: { query?: string, items?: any[] }) {
  let newsItems = items || [];

  // Fallback if empty
  if (!Array.isArray(newsItems) || newsItems.length === 0) {
    newsItems = [
      { title: "No news data provided.", source: "System", time: "Just now" }
    ];
  }

  return (
    <div className="p-4 text-megan-text-main">
      <h3 className="text-sm mb-4 text-megan-cyan flex items-center gap-2">
        <Newspaper size={16} /> Breaking News: {query || "Top Stories"}
      </h3>
      
      {newsItems.map((item, i) => (
        <div key={i} className="mb-3 p-3 bg-black/30 border border-megan-border rounded">
          <div className="text-xs font-bold mb-1">
            {item.title}
          </div>
          <div className="text-[10px] text-megan-text-dim flex justify-between">
            <span>{item.source || "Web"}</span>
            <span>{item.time || ""}</span>
          </div>
        </div>
      ))}
    </div>
  );
}
