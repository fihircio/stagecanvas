"use client";

import React, { useEffect, useRef, useState } from 'react';

interface LiveMonitorProps {
    streamUrl?: string;
    nodeId: string;
}

export const LiveMonitor: React.FC<LiveMonitorProps> = ({ streamUrl, nodeId }) => {
    const videoRef = useRef<HTMLVideoElement>(null);
    const [isConnected, setIsConnected] = useState(false);
    const [error, setError] = useState<string | null>(null);

    useEffect(() => {
        if (!videoRef.current) return;

        let pc: RTCPeerConnection | null = null;

        const connect = async () => {
            try {
                pc = new RTCPeerConnection({
                    iceServers: [{ urls: 'stun:stun.l.google.com:19302' }]
                });

                pc.ontrack = (event) => {
                    if (videoRef.current) {
                        videoRef.current.srcObject = event.streams[0];
                    }
                };

                pc.onconnectionstatechange = () => {
                    if (pc?.connectionState === 'connected') {
                        setIsConnected(true);
                        setError(null);
                    } else if (pc?.connectionState === 'failed') {
                        setError('WebRTC Connection Failed');
                    }
                };

                // Fetch offer from render-node signaling server
                const response = await fetch(`${streamUrl}/offer`, {
                    method: 'POST',
                    body: JSON.stringify({
                        sdp: "", // Initial probe or just request offer
                        type: "offer"
                    }),
                    headers: { 'Content-Type': 'application/json' }
                });

                const offer = await response.json();
                await pc.setRemoteDescription(new RTCSessionDescription(offer));

                const answer = await pc.createAnswer();
                await pc.setLocalDescription(answer);

                // Send answer back (simplified signaling; usually you need to POST the answer back)
                // In our current render-node implementation, handle_answer is internal, 
                // so we might need to adjust the backend signaling or this flow.
                // Assuming the backend handles everything in the /offer call for simplicity in this stub.

            } catch (err) {
                console.error('[live-monitor] Connection error:', err);
                setError('Failed to connect to stream');
            }
        };

        connect();

        return () => {
            if (pc) {
                pc.close();
            }
            setIsConnected(false);
        };
    }, [nodeId, streamUrl]);

    return (
        <div className="relative w-full aspect-video bg-black rounded-lg overflow-hidden border border-slate-700 shadow-2xl group">
            <div className="absolute inset-0 flex items-center justify-center">
                {!isConnected && !error && (
                    <div className="flex flex-col items-center gap-3">
                        <div className="w-8 h-8 border-4 border-indigo-500 border-t-transparent rounded-full animate-spin" />
                        <span className="text-slate-400 text-sm font-medium">Connecting to Live Feed...</span>
                    </div>
                )}
                {error && (
                    <div className="flex flex-col items-center gap-3 text-red-400">
                        <span className="text-sm font-medium">{error}</span>
                        <button onClick={() => setError(null)} className="text-xs underline">Retry</button>
                    </div>
                )}
                {isConnected && (
                    <video
                        ref={videoRef}
                        autoPlay
                        muted
                        playsInline
                        className="w-full h-full object-contain"
                        poster="/preview-placeholder.png"
                    />
                )}
            </div>

            {/* Overlays */}
            <div className="absolute top-4 left-4 flex items-center gap-2">
                <div className={`w-2 h-2 rounded-full ${isConnected ? 'bg-emerald-500 animate-pulse' : 'bg-slate-500'}`} />
                <span className="text-[10px] font-bold tracking-widest uppercase text-white drop-shadow-md">
                    LIVE • {nodeId}
                </span>
            </div>

            <div className="absolute bottom-4 right-4 opacity-0 group-hover:opacity-100 transition-opacity">
                <button className="px-3 py-1 bg-white/10 hover:bg-white/20 backdrop-blur-md border border-white/20 rounded text-[10px] font-bold text-white uppercase tracking-wider">
                    Expand
                </button>
            </div>

            {/* Precision Frame Overlay Mock */}
            <div className="absolute bottom-4 left-4 text-[10px] font-mono text-emerald-400/80 drop-shadow-md opacity-0 group-hover:opacity-100 transition-opacity">
                LATENCY: 42ms | FR: 60.0FPS
            </div>
        </div>
    );
};

export default LiveMonitor;
