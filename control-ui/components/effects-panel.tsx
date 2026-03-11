"use client";

import React, { useState, useCallback } from 'react';

// --- Types ---
export interface ColorCorrectionParams {
  brightness: number;  // 0.0 – 2.0, default 1.0
  contrast: number;    // 0.0 – 2.0, default 1.0
  saturation: number;  // 0.0 – 2.0, default 1.0
}

export interface EffectConfig {
  type: 'color_correction' | 'blur' | 'lut';
  enabled: boolean;
  params: Record<string, number | string>;
}

interface EffectsPanelProps {
  layerId: string;
  wsUrl?: string; // Optional: can be used for direct WS, but we default to Orchestrator REST
}

const LUT_OPTIONS = ['None', 'Rec709_to_sRGB', 'HLG_to_sRGB', 'Filmic', 'Vintage', 'ColdBlue'];

// --- Sub-components ---
function SectionHeader({ title }: { title: string }) {
  return (
    <div style={{ borderBottom: '1px solid #333', paddingBottom: '6px', marginBottom: '10px' }}>
      <span style={{ fontSize: '11px', fontWeight: 700, letterSpacing: '0.1em', textTransform: 'uppercase', color: '#aaa' }}>
        {title}
      </span>
    </div>
  );
}

function SliderRow({
  label, value, min, max, step, onChange
}: { label: string; value: number; min: number; max: number; step: number; onChange: (v: number) => void }) {
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: '10px', marginBottom: '8px' }}>
      <span style={{ width: '90px', fontSize: '12px', color: '#ccc', flexShrink: 0 }}>{label}</span>
      <input
        type="range"
        min={min}
        max={max}
        step={step}
        value={value}
        onChange={(e) => onChange(parseFloat(e.target.value))}
        style={{ flex: 1, accentColor: '#0070f3' }}
      />
      <span style={{ width: '38px', fontSize: '12px', color: '#eee', textAlign: 'right', fontVariantNumeric: 'tabular-nums' }}>
        {value.toFixed(2)}
      </span>
    </div>
  );
}

function Toggle({ label, value, onChange }: { label: string; value: boolean; onChange: (v: boolean) => void }) {
  return (
    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '12px' }}>
      <span style={{ fontSize: '13px', color: '#ddd' }}>{label}</span>
      <div
        onClick={() => onChange(!value)}
        style={{
          width: '40px', height: '22px', borderRadius: '11px', cursor: 'pointer', position: 'relative',
          background: value ? '#0070f3' : '#444', transition: 'background 0.2s',
        }}
      >
        <div style={{
          position: 'absolute', top: '3px', left: value ? '21px' : '3px',
          width: '16px', height: '16px', borderRadius: '50%',
          background: '#fff', transition: 'left 0.2s',
        }} />
      </div>
    </div>
  );
}

// --- Main Component ---
export function EffectsPanel({ layerId, wsUrl }: EffectsPanelProps) {
  const [ccEnabled, setCcEnabled] = useState(true);
  const [blurEnabled, setBlurEnabled] = useState(false);
  const [lutEnabled, setLutEnabled] = useState(false);

  const [brightness, setBrightness] = useState(1.0);
  const [contrast, setContrast] = useState(1.0);
  const [saturation, setSaturation] = useState(1.0);
  const [blurRadius, setBlurRadius] = useState(0.0);
  const [selectedLut, setSelectedLut] = useState('None');

  const [status, setStatus] = useState<string | null>(null);

  const buildPayload = useCallback(() => {
    const effects: EffectConfig[] = [
      {
        type: 'color_correction',
        enabled: ccEnabled,
        params: { brightness, contrast, saturation },
      },
      {
        type: 'blur',
        enabled: blurEnabled,
        params: { radius: blurRadius },
      },
      {
        type: 'lut',
        enabled: lutEnabled && selectedLut !== 'None',
        params: { lut_name: selectedLut },
      },
    ];
    return { layer_id: layerId, effects };
  }, [layerId, ccEnabled, brightness, contrast, saturation, blurEnabled, blurRadius, lutEnabled, selectedLut]);

  const applyEffects = useCallback(async () => {
    const payload = buildPayload();
    // Default to localhost:18010 if not provided
    const baseUrl = process.env.NEXT_PUBLIC_ORCHESTRATION_HTTP || 'http://localhost:18010';
    try {
      setStatus('Applying...');
      const res = await fetch(`${baseUrl}/api/v1/operators/update_layers`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ payload: { layers: [payload] }, node_ids: [] }),
      });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      setStatus('✓ Applied');
    } catch (e: any) {
      setStatus(`Error: ${e.message}`);
    }
    setTimeout(() => setStatus(null), 2500);
  }, [buildPayload]);

  const panelStyle: React.CSSProperties = {
    background: '#1a1a2e',
    border: '1px solid #2a2a4a',
    borderRadius: '10px',
    padding: '16px',
    width: '280px',
    color: '#fff',
    fontFamily: 'Inter, -apple-system, sans-serif',
    boxShadow: '0 8px 32px rgba(0,0,0,0.5)',
    userSelect: 'none',
  };

  return (
    <div style={panelStyle}>
      {/* Header */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '16px' }}>
        <span style={{ fontSize: '14px', fontWeight: 700, color: '#e0e8ff' }}>🎨 Effects</span>
        <span style={{ fontSize: '11px', color: '#666', fontFamily: 'monospace' }}>{layerId}</span>
      </div>

      {/* Color Correction */}
      <SectionHeader title="Color Correction" />
      <Toggle label="Enable" value={ccEnabled} onChange={setCcEnabled} />
      {ccEnabled && (
        <div style={{ opacity: ccEnabled ? 1 : 0.4, pointerEvents: ccEnabled ? 'auto' : 'none' }}>
          <SliderRow label="Brightness" value={brightness} min={0} max={2} step={0.01} onChange={setBrightness} />
          <SliderRow label="Contrast"   value={contrast}   min={0} max={2} step={0.01} onChange={setContrast} />
          <SliderRow label="Saturation" value={saturation} min={0} max={2} step={0.01} onChange={setSaturation} />
        </div>
      )}

      {/* Blur */}
      <SectionHeader title="Blur" />
      <Toggle label="Enable" value={blurEnabled} onChange={setBlurEnabled} />
      {blurEnabled && (
        <SliderRow label="Radius (px)" value={blurRadius} min={0} max={50} step={0.5} onChange={setBlurRadius} />
      )}

      {/* LUT */}
      <SectionHeader title="LUT" />
      <Toggle label="Enable" value={lutEnabled} onChange={setLutEnabled} />
      {lutEnabled && (
        <div style={{ marginBottom: '12px' }}>
          <select
            value={selectedLut}
            onChange={(e) => setSelectedLut(e.target.value)}
            style={{
              width: '100%',
              background: '#222244',
              color: '#fff',
              border: '1px solid #444',
              borderRadius: '4px',
              padding: '6px 8px',
              fontSize: '13px',
            }}
          >
            {LUT_OPTIONS.map((lut) => (
              <option key={lut} value={lut}>{lut}</option>
            ))}
          </select>
        </div>
      )}

      {/* Apply Button */}
      <button
        onClick={applyEffects}
        style={{
          width: '100%',
          marginTop: '8px',
          padding: '10px',
          background: 'linear-gradient(135deg, #0070f3, #7928ca)',
          color: '#fff',
          border: 'none',
          borderRadius: '6px',
          fontSize: '13px',
          fontWeight: 700,
          cursor: 'pointer',
          transition: 'opacity 0.2s',
        }}
        onMouseEnter={(e) => (e.currentTarget.style.opacity = '0.85')}
        onMouseLeave={(e) => (e.currentTarget.style.opacity = '1')}
      >
        ⚡ Apply in Real-Time
      </button>

      {status && (
        <div style={{
          marginTop: '8px',
          padding: '6px 10px',
          borderRadius: '4px',
          fontSize: '12px',
          textAlign: 'center',
          background: status.startsWith('Error') ? '#4a1010' : '#103a10',
          color: status.startsWith('Error') ? '#ff8888' : '#88ff88',
        }}>
          {status}
        </div>
      )}
    </div>
  );
}
