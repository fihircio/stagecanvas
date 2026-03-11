import React from 'react';
import { EffectsPanel } from '../../components/effects-panel';

export default function EffectsPage() {
  return (
    <div style={{
      minHeight: '100vh',
      background: '#0d0d1a',
      display: 'flex',
      alignItems: 'flex-start',
      justifyContent: 'flex-start',
      padding: '32px',
      gap: '24px',
      flexWrap: 'wrap',
    }}>
      <div>
        <h2 style={{ color: '#aaa', fontFamily: 'Inter, sans-serif', fontSize: '12px', textTransform: 'uppercase', letterSpacing: '0.1em', margin: '0 0 16px' }}>
          Layer Effects Editor
        </h2>
        {/* Panel for layer-1 */}
        <EffectsPanel layerId="layer-1" />
      </div>
    </div>
  );
}
