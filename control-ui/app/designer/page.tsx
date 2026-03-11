"use client";

import { NodeGraph } from '../../components/node-graph';
import dynamic from 'next/dynamic';
import { useState } from 'react';

// Dynamically import StagePreviz with SSR disabled since it uses WebGL/window
const StagePreviz = dynamic(() => import('../../components/stage-previz').then(mod => mod.StagePreviz), { ssr: false });

export default function DesignerPage() {
    // In a real app this might come from a live monitor context, but we'll use a sample or empty for now
    const [streamUrl, setStreamUrl] = useState<string | undefined>(undefined);

    return (
        <div style={{ width: '100vw', height: '100vh', display: 'flex', flexDirection: 'column' }}>
            <header style={{ padding: '10px 20px', background: '#111', color: '#fff', borderBottom: '1px solid #333', display: 'flex', justifyContent: 'space-between' }}>
                <h1 style={{ fontSize: '1.2rem', margin: 0 }}>StageCanvas Designer (Phase 1 USP)</h1>
                <div>
                  <button onClick={() => setStreamUrl('http://commondatastorage.googleapis.com/gtv-videos-bucket/sample/BigBuckBunny.mp4')} style={{ background: '#333', color: 'white', border: '1px solid #555', padding: '4px 8px', borderRadius: '4px', cursor: 'pointer', fontSize: '12px' }}>Test Video Feed</button>
                  <button onClick={() => setStreamUrl(undefined)} style={{ background: '#333', color: 'white', border: '1px solid #555', padding: '4px 8px', borderRadius: '4px', cursor: 'pointer', fontSize: '12px', marginLeft: '8px' }}>Clear Feed</button>
                </div>
            </header>
            <main style={{ flex: 1, backgroundColor: '#0a0a0a', display: 'flex' }}>
                <div style={{ flex: 1, borderRight: '1px solid #333' }}>
                    <NodeGraph />
                </div>
                <div style={{ width: '40%', minWidth: '400px', display: 'flex', flexDirection: 'column', backgroundColor: '#151515', padding: '16px' }}>
                    <h2 style={{ color: '#fff', fontSize: '1rem', marginTop: 0, marginBottom: '16px' }}>3D Pre-Viz Stage Simulator</h2>
                    <div style={{ flex: 1, width: '100%', borderRadius: '8px', overflow: 'hidden' }}>
                        <StagePreviz webRtcStreamUrl={streamUrl} width={undefined} height={undefined} />
                    </div>
                </div>
            </main>
        </div>
    );
}

