/**
 * KnowledgeBase — shows stored persona preferences and recent memories.
 */

import { useEffect, useState } from 'react';

interface Preference {
  key: string;
  value: string;
}

interface Memory {
  id: number;
  type: string;
  content: string;
  created_at: string;
}

const API_BASE = `http://${window.location.hostname}:8000/api`;

export function KnowledgeBase() {
  const [preferences, setPreferences] = useState<Preference[]>([]);
  const [memories, setMemories] = useState<Memory[]>([]);
  const [searchQuery, setSearchQuery] = useState('');
  const [searchResults, setSearchResults] = useState<any[]>([]);

  useEffect(() => {
    const fetchData = async () => {
      try {
        const [personaRes, memRes] = await Promise.all([
          fetch(`${API_BASE}/persona`),
          fetch(`${API_BASE}/memories?limit=15`),
        ]);
        const personaData = await personaRes.json();
        const memData = await memRes.json();

        const prefs = Object.entries(personaData.preferences || {}).map(([key, value]) => ({
          key,
          value: value as string,
        }));
        setPreferences(prefs);
        setMemories(memData.memories || []);
      } catch (e) {
        console.error('KnowledgeBase fetch error:', e);
      }
    };

    fetchData();
    const interval = setInterval(fetchData, 10000);
    return () => clearInterval(interval);
  }, []);

  const handleSearch = async () => {
    if (!searchQuery.trim()) return;
    try {
      const res = await fetch(`${API_BASE}/memories/search`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ query: searchQuery, limit: 10 }),
      });
      const data = await res.json();
      setSearchResults(data.results || []);
    } catch (e) {
      console.error('Search error:', e);
    }
  };

  return (
    <div className="h-full overflow-y-auto p-5 space-y-5">
      {/* Persona Preferences */}
      <section>
        <h3 className="text-xs tracking-widest text-megan-accent mb-3 text-glow-purple">⊡ USER PERSONA</h3>
        {preferences.length === 0 ? (
          <p className="text-[11px] text-megan-text-muted">No preferences stored yet. Tell Megan about yourself!</p>
        ) : (
          <div className="space-y-1.5">
            {preferences.map((pref) => (
              <div key={pref.key} className="flex items-start gap-2 border border-megan-border rounded px-3 py-2 bg-megan-panel/30">
                <span className="text-[10px] tracking-wider text-megan-cyan shrink-0 mt-0.5">{pref.key.toUpperCase().replace(/_/g, ' ')}</span>
                <span className="text-[11px] text-megan-text">{pref.value}</span>
              </div>
            ))}
          </div>
        )}
      </section>

      {/* Semantic Memory Search */}
      <section>
        <h3 className="text-xs tracking-widest text-megan-cyan mb-3 text-glow-cyan">⊡ MEMORY SEARCH</h3>
        <div className="flex gap-2 mb-3">
          <input
            type="text"
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && handleSearch()}
            placeholder="Search memories..."
            className="flex-1 bg-transparent text-[11px] text-megan-text placeholder:text-megan-text-muted outline-none border border-megan-border rounded px-3 py-1.5 focus:border-megan-accent transition-all"
          />
          <button
            onClick={handleSearch}
            className="px-3 py-1.5 text-[10px] tracking-wider border border-megan-border text-megan-text-dim hover:text-megan-accent hover:border-megan-accent transition-all"
          >
            SEARCH
          </button>
        </div>
        {searchResults.length > 0 && (
          <div className="space-y-1.5 mb-4">
            {searchResults.map((r, i) => (
              <div key={i} className="border border-megan-accent/20 rounded px-3 py-2 bg-megan-accent/5">
                <p className="text-[11px] text-megan-text leading-relaxed">{r.content?.slice(0, 200)}</p>
                <p className="text-[9px] text-megan-text-muted mt-1">Distance: {r.distance?.toFixed(3)}</p>
              </div>
            ))}
          </div>
        )}
      </section>

      {/* Recent Memories */}
      <section>
        <h3 className="text-xs tracking-widest text-megan-text-dim mb-3">⊟ RECENT MEMORIES</h3>
        {memories.length === 0 ? (
          <p className="text-[11px] text-megan-text-muted">No memories stored yet.</p>
        ) : (
          <div className="space-y-1.5">
            {memories.map((mem) => (
              <div key={mem.id} className="border border-megan-border rounded px-3 py-2 bg-megan-panel/30">
                <div className="flex items-center justify-between mb-1">
                  <span className={`text-[9px] tracking-wider px-1.5 py-0.5 rounded ${
                    mem.type === 'conversation' ? 'bg-megan-accent/10 text-megan-accent' :
                    mem.type === 'preference' ? 'bg-megan-cyan/10 text-megan-cyan' :
                    'bg-megan-green/10 text-megan-green'
                  }`}>{mem.type.toUpperCase()}</span>
                  <span className="text-[9px] text-megan-text-muted">
                    {new Date(mem.created_at).toLocaleDateString()}
                  </span>
                </div>
                <p className="text-[11px] text-megan-text leading-relaxed">{mem.content.slice(0, 150)}</p>
              </div>
            ))}
          </div>
        )}
      </section>
    </div>
  );
}
