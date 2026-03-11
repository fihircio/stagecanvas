"use client";

import React, { useEffect, useState } from 'react';
import { auth } from '../lib/auth';

export interface MappingModalProps {
  open: boolean;
  onClose: () => void;
  targetLayerId: string;
  targetProperty: string;
}

export function MappingModal({ open, onClose, targetLayerId, targetProperty }: MappingModalProps) {
  const [isListening, setIsListening] = useState(false);
  const [errorDesc, setErrorDesc] = useState<string | null>(null);

  useEffect(() => {
    if (!open) return;
    setIsListening(false);
    setErrorDesc(null);

    const baseUrl = process.env.NEXT_PUBLIC_ORCHESTRATION_HTTP || 'http://localhost:18010';

    const startLearning = async () => {
      try {
        const res = await auth.fetch(`${baseUrl}/api/v1/io/learn/start`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ target_layer_id: targetLayerId, target_property: targetProperty })
        });
        if (res.ok) {
          setIsListening(true);
        } else {
          setErrorDesc(`Failed to start: HTTP ${res.status}`);
        }
      } catch (err: any) {
        setErrorDesc(err.message || 'Network error');
      }
    };

    startLearning();

    return () => {
      // Cleanup on unmount or close
      auth.fetch(`${baseUrl}/api/v1/io/learn/stop`, { method: 'POST' }).catch(() => {});
    };
  }, [open, targetLayerId, targetProperty]);

  if (!open) return null;

  return (
    <div style={{
      position: 'fixed',
      top: 0, left: 0, right: 0, bottom: 0,
      background: 'rgba(0,0,0,0.7)',
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'center',
      zIndex: 9999
    }}>
      <div style={{
        background: '#1a1a2e',
        border: '1px solid #2a2a4a',
        borderRadius: '10px',
        width: '320px',
        padding: '24px',
        color: '#fff',
        fontFamily: 'Inter, -apple-system, sans-serif',
        boxShadow: '0 8px 32px rgba(0,0,0,0.5)',
        display: 'flex',
        flexDirection: 'column',
        gap: '16px'
      }}>
        <h3 style={{ margin: 0, fontSize: '16px', fontWeight: 600 }}>Learn Mapping</h3>
        
        <div style={{ fontSize: '13px', color: '#ccc' }}>
          Move a hardware fader, turn a knob, or press a button to map it to:<br/>
          <strong style={{ color: '#0070f3' }}>{targetProperty}</strong> on layer <strong>{targetLayerId}</strong>
        </div>

        <div style={{
          background: '#111122',
          padding: '16px',
          borderRadius: '6px',
          textAlign: 'center',
          minHeight: '60px',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          fontSize: '12px'
        }}>
          {errorDesc ? (
             <span style={{ color: '#ff4444' }}>{errorDesc}</span>
          ) : isListening ? (
             <span style={{ color: '#00ff88', animation: 'pulse 1s infinite alternate' }}>
               Listening for MIDI/OSC...
             </span>
          ) : (
             <span style={{ color: '#888' }}>Initializing...</span>
          )}
        </div>

        <button 
          onClick={onClose}
          style={{
            background: '#ffffff',
            color: '#000',
            border: 'none',
            padding: '8px 16px',
            borderRadius: '4px',
            fontSize: '13px',
            fontWeight: 600,
            cursor: 'pointer',
            alignSelf: 'flex-end',
            marginTop: '8px'
          }}
        >
          Close
        </button>
      </div>
{/* Inject simple pulse animation via inline style tag for convenience */}
      <style>{`
        @keyframes pulse {
          0% { opacity: 0.5; }
          100% { opacity: 1; }
        }
      `}</style>
    </div>
  );
}
