import React from 'react';
import { CloudRain, Wind, Droplets } from 'lucide-react';

export function WeatherWindow({ query }: { query?: string }) {
  return (
    <div style={{ padding: '20px', color: 'var(--text-main)', textAlign: 'center' }}>
      <h3 style={{ fontSize: '12px', color: 'var(--text-dim)', marginBottom: '10px' }}>
        {query ? query.toUpperCase() : "LOCAL WEATHER"}
      </h3>
      
      <div style={{ fontSize: '48px', fontWeight: 'bold', color: 'var(--color-cyan)', textShadow: '0 0 10px var(--color-cyan-glow)' }}>
        24°C
      </div>
      
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '8px', fontSize: '14px', marginBottom: '20px' }}>
        <CloudRain size={16} /> Light Rain
      </div>
      
      <div style={{ display: 'flex', justifyContent: 'space-around', padding: '10px 0', borderTop: '1px solid var(--panel-border)', borderBottom: '1px solid var(--panel-border)' }}>
        <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: '4px' }}>
          <Wind size={14} color="var(--text-dim)" />
          <span style={{ fontSize: '10px' }}>12 km/h</span>
        </div>
        <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: '4px' }}>
          <Droplets size={14} color="var(--text-dim)" />
          <span style={{ fontSize: '10px' }}>84%</span>
        </div>
      </div>
      
      <div style={{ display: 'flex', justifyContent: 'space-between', marginTop: '15px', fontSize: '10px' }}>
        <div>
          <div style={{ color: 'var(--text-dim)' }}>TOMORROW</div>
          <div>22°C ☁️</div>
        </div>
        <div>
          <div style={{ color: 'var(--text-dim)' }}>FRIDAY</div>
          <div>26°C ☀️</div>
        </div>
        <div>
          <div style={{ color: 'var(--text-dim)' }}>SATURDAY</div>
          <div>25°C ⛅</div>
        </div>
      </div>
    </div>
  );
}
