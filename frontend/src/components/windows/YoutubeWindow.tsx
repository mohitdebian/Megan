import React, { useState, useEffect } from 'react';
import { MonitorPlay, ExternalLink, Play, Loader } from 'lucide-react';

export function YoutubeWindow({ query, items, content }: { query?: string, items?: any[], content?: string }) {
  const [videoId, setVideoId] = useState<string | null>(null);
  const [videoTitle, setVideoTitle] = useState<string>('');
  const [videoChannel, setVideoChannel] = useState<string>('');
  const [loading, setLoading] = useState(true);

  const extractVideoId = (url: string): string | null => {
    if (!url) return null;
    const patterns = [
      /(?:youtube\.com\/watch\?v=)([a-zA-Z0-9_-]{11})/,
      /(?:youtu\.be\/)([a-zA-Z0-9_-]{11})/,
      /(?:youtube\.com\/embed\/)([a-zA-Z0-9_-]{11})/,
      /(?:youtube\.com\/shorts\/)([a-zA-Z0-9_-]{11})/,
    ];
    for (const pattern of patterns) {
      const match = url.match(pattern);
      if (match) return match[1];
    }
    if (/^[a-zA-Z0-9_-]{11}$/.test(url)) return url;
    return null;
  };

  // Clean up channel-style queries: strip " - YouTube", "YouTube", etc.
  const cleanQuery = (q: string): string => {
    return q
      .replace(/\s*-\s*YouTube\s*$/i, '')
      .replace(/\s*YouTube\s*$/i, '')
      .replace(/\s*\|\s*YouTube\s*$/i, '')
      .trim();
  };

  useEffect(() => {
    // First: check if items already have a video URL
    const vid = items?.[0] || {};
    const directUrl = vid.url || content || '';
    const directId = extractVideoId(directUrl);

    if (directId) {
      setVideoId(directId);
      setVideoTitle(vid.title || query || 'Video');
      setVideoChannel(vid.channel || '');
      setLoading(false);
      return;
    }

    // Second: search via our backend proxy (no CORS issues)
    const searchTerm = cleanQuery(query || vid.title || '');
    if (!searchTerm) {
      setLoading(false);
      return;
    }

    setVideoTitle(searchTerm);

    const fetchVideo = async () => {
      try {
        const res = await fetch(`/api/youtube/search?q=${encodeURIComponent(searchTerm)}&count=1`);
        if (!res.ok) throw new Error('API error');
        const data = await res.json();

        if (data.results && data.results.length > 0) {
          const top = data.results[0];
          setVideoId(top.videoId);
          setVideoTitle(top.title || searchTerm);
          setVideoChannel(top.channel || '');
        }
      } catch (e) {
        console.warn('YouTube search proxy failed:', e);
      } finally {
        setLoading(false);
      }
    };

    fetchVideo();
  }, [query, items, content]);

  const searchQuery = encodeURIComponent(query || videoTitle || 'video');

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100%', background: '#000' }}>
      {loading ? (
        <div style={{ flex: 1, display: 'flex', alignItems: 'center', justifyContent: 'center', flexDirection: 'column', gap: '10px' }}>
          <Loader size={24} style={{ color: '#f05', animation: 'spin 1s linear infinite' }} />
          <span style={{ fontSize: '11px', color: 'rgba(255,255,255,0.5)' }}>Finding video...</span>
          <style>{`@keyframes spin { from { transform: rotate(0deg); } to { transform: rotate(360deg); } }`}</style>
        </div>
      ) : videoId ? (
        <div style={{ flex: 1, minHeight: 0 }}>
          <iframe
            width="100%"
            height="100%"
            src={`https://www.youtube.com/embed/${videoId}?rel=0`}
            title={videoTitle}
            frameBorder="0"
            allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture"
            allowFullScreen
            style={{ display: 'block' }}
          />
        </div>
      ) : (
        <div 
          style={{ flex: 1, display: 'flex', alignItems: 'center', justifyContent: 'center', flexDirection: 'column', gap: '12px', cursor: 'pointer' }}
          onClick={() => window.open(`https://www.youtube.com/results?search_query=${searchQuery}`, '_blank')}
        >
          <Play size={48} style={{ color: 'rgba(255,0,85,0.6)' }} />
          <span style={{ fontSize: '12px', color: 'rgba(255,255,255,0.5)' }}>Click to search on YouTube</span>
        </div>
      )}

      {/* Info Bar */}
      <div style={{ 
        padding: '8px 12px', 
        background: 'rgba(0,0,0,0.8)', 
        borderTop: '1px solid rgba(0,255,255,0.15)',
        display: 'flex',
        alignItems: 'center',
        gap: '8px'
      }}>
        <MonitorPlay size={14} style={{ color: '#f05', flexShrink: 0 }} />
        <div style={{ flex: 1, minWidth: 0 }}>
          <div style={{ fontSize: '11px', fontWeight: 'bold', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', color: '#e0f8f8' }}>
            {videoTitle || query}
          </div>
          {videoChannel && (
            <div style={{ fontSize: '9px', color: 'rgba(112,152,152,1)', marginTop: '1px' }}>{videoChannel}</div>
          )}
        </div>
        <a 
          href={videoId ? `https://www.youtube.com/watch?v=${videoId}` : `https://www.youtube.com/results?search_query=${searchQuery}`}
          target="_blank" 
          rel="noopener noreferrer"
          style={{ 
            color: '#f05', fontSize: '10px', textDecoration: 'none',
            border: '1px solid rgba(255,0,85,0.3)', padding: '3px 8px',
            borderRadius: '4px', display: 'flex', alignItems: 'center',
            gap: '4px', flexShrink: 0
          }}
        >
          <ExternalLink size={10} /> YouTube
        </a>
      </div>
    </div>
  );
}
