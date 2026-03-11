"use client";

import React, { useState, useEffect, useCallback } from 'react';

// --- Types ---
interface Cue {
  rule_id: string;
  name: string;
  emoji?: string;
  color?: string;
}

interface MobileCuePanelProps {
  orchestrationUrl?: string;
}

// Default show-day cue palette (top 8)
const DEFAULT_CUES: Cue[] = [
  { rule_id: 'cue-intro',     name: 'Intro',       emoji: '🎬', color: '#7928ca' },
  { rule_id: 'cue-act1',      name: 'Act 1',       emoji: '▶️',  color: '#0070f3' },
  { rule_id: 'cue-act2',      name: 'Act 2',       emoji: '▶️',  color: '#0070f3' },
  { rule_id: 'cue-climax',    name: 'Climax',      emoji: '🔥', color: '#e6302a' },
  { rule_id: 'cue-blackout',  name: 'Blackout',    emoji: '⬛', color: '#222' },
  { rule_id: 'cue-spotlight', name: 'Spotlight',   emoji: '💡', color: '#e6a800' },
  { rule_id: 'cue-outro',     name: 'Outro',       emoji: '🎭', color: '#1a8a5e' },
  { rule_id: 'cue-reset',     name: 'Reset',       emoji: '🔄', color: '#555' },
];

// --- Main Component ---
export function MobileCuePanel({ orchestrationUrl }: MobileCuePanelProps) {
  const baseUrl = orchestrationUrl || process.env.NEXT_PUBLIC_ORCHESTRATION_HTTP || 'http://localhost:18010';
  const [cues, setCues] = useState<Cue[]>(DEFAULT_CUES);
  const [firing, setFiring] = useState<string | null>(null);
  const [lastFired, setLastFired] = useState<string | null>(null);

  // Fetch live cue list from API (the top 8 registered trigger rules)
  useEffect(() => {
    const fetchCues = async () => {
      try {
        const res = await fetch(`${baseUrl}/api/v1/triggers`);
        if (!res.ok) return;
        const data = await res.json();
        const rules: Cue[] = (data.rules || []).slice(0, 8).map((r: any) => ({
          rule_id: r.rule_id,
          name: r.name || r.rule_id,
          emoji: '▶️',
          color: '#0070f3',
        }));
        if (rules.length > 0) setCues(rules);
      } catch {
        // Silently fall back to defaults
      }
    };
    fetchCues();
  }, [baseUrl]);

  const fireCue = useCallback(async (cue: Cue) => {
    if (firing) return;
    setFiring(cue.rule_id);
    try {
      await fetch(`${baseUrl}/api/v1/triggers/${cue.rule_id}/fire`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ rule_id: cue.rule_id, payload: {} }),
      });
      setLastFired(cue.name);
      setTimeout(() => setLastFired(null), 2000);
    } catch {
      // Silently ignore – show-day reliability
    } finally {
      setTimeout(() => setFiring(null), 300);
    }
  }, [baseUrl, firing]);

  return (
    <div style={{
      minHeight: '100dvh',
      background: 'linear-gradient(160deg, #0a0a1a 0%, #0d1a2e 100%)',
      display: 'flex',
      flexDirection: 'column',
      fontFamily: 'Inter, -apple-system, sans-serif',
      WebkitTapHighlightColor: 'transparent',
    }}>
      {/* Header */}
      <div style={{
        padding: '20px 20px 12px',
        borderBottom: '1px solid #1e2a3a',
        display: 'flex',
        justifyContent: 'space-between',
        alignItems: 'center',
      }}>
        <div>
          <div style={{ fontSize: '18px', fontWeight: 800, color: '#e0e8ff' }}>🎭 Cue Panel</div>
          <div style={{ fontSize: '11px', color: '#5a6a7a', marginTop: '2px' }}>StageCanvas Mobile</div>
        </div>
        {lastFired && (
          <div style={{
            background: '#0a3a1a',
            border: '1px solid #1a6a2a',
            borderRadius: '20px',
            padding: '4px 12px',
            fontSize: '12px',
            color: '#4aff8a',
            fontWeight: 600,
            animation: 'fadeIn 0.2s ease',
          }}>
            ✓ {lastFired}
          </div>
        )}
      </div>

      {/* Cue Grid */}
      <div style={{
        display: 'grid',
        gridTemplateColumns: '1fr 1fr',
        gap: '12px',
        padding: '16px',
        flex: 1,
      }}>
        {cues.map((cue) => {
          const isFiring = firing === cue.rule_id;
          return (
            <button
              key={cue.rule_id}
              id={`cue-btn-${cue.rule_id}`}
              onClick={() => fireCue(cue)}
              style={{
                background: isFiring
                  ? `${cue.color || '#0070f3'}22`
                  : `linear-gradient(145deg, ${cue.color || '#0070f3'}33, ${cue.color || '#0070f3'}11)`,
                border: `1.5px solid ${cue.color || '#0070f3'}66`,
                borderRadius: '14px',
                padding: '20px 12px',
                cursor: 'pointer',
                display: 'flex',
                flexDirection: 'column',
                alignItems: 'center',
                justifyContent: 'center',
                gap: '8px',
                minHeight: '100px',
                transform: isFiring ? 'scale(0.94)' : 'scale(1)',
                transition: 'transform 0.15s ease, background 0.15s ease, box-shadow 0.15s ease',
                boxShadow: isFiring
                  ? `0 0 20px ${cue.color || '#0070f3'}55`
                  : '0 2px 8px rgba(0,0,0,0.4)',
                WebkitUserSelect: 'none',
              }}
            >
              <span style={{ fontSize: '28px', lineHeight: 1 }}>{cue.emoji || '▶️'}</span>
              <span style={{
                fontSize: '13px',
                fontWeight: 700,
                color: '#d0e0ff',
                textTransform: 'uppercase',
                letterSpacing: '0.05em',
              }}>
                {cue.name}
              </span>
            </button>
          );
        })}
      </div>

      {/* Footer */}
      <div style={{
        padding: '12px 20px',
        borderTop: '1px solid #1e2a3a',
        display: 'flex',
        justifyContent: 'center',
      }}>
        <span style={{ fontSize: '11px', color: '#3a4a5a' }}>Tap cue to fire instantly · StageCanvas v1.0</span>
      </div>
    </div>
  );
}
