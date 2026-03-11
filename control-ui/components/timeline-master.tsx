"use client";

import { useState, useRef, useEffect, MouseEvent, DragEvent } from 'react';
import { TimelineSnapshot, TimelineTrack, TimelineClip, MediaAsset } from '../lib/types';

interface TimelineMasterProps {
    snapshot: TimelineSnapshot | null;
    onSeek: (ms: number) => void;
    onDropAsset: (trackId: string, asset: any, ms: number) => void;
}

export function TimelineMaster({ snapshot, onSeek, onDropAsset }: TimelineMasterProps) {
    const [zoom, setZoom] = useState(1.0); // pixels per ms
    const scrollRef = useRef<HTMLDivElement>(null);
    const [isDraggingPlayhead, setIsDraggingPlayhead] = useState(false);

    if (!snapshot) return <div className="timeline-empty">No show loaded</div>;

    const pixelsPerMs = 0.1 * zoom; // default 0.1px = 1ms -> 100px = 1sec
    const totalWidth = snapshot.duration_ms * pixelsPerMs;
    const playheadPos = snapshot.playhead_ms * pixelsPerMs;

    const handleTimelineClick = (e: MouseEvent) => {
        if (!scrollRef.current) return;
        const rect = scrollRef.current.getBoundingClientRect();
        const x = e.clientX - rect.left + scrollRef.current.scrollLeft;
        const ms = x / pixelsPerMs;
        onSeek(Math.max(0, Math.min(snapshot.duration_ms, ms)));
    };

    const onWheel = (e: React.WheelEvent) => {
        if (e.ctrlKey || e.metaKey) {
            e.preventDefault();
            setZoom(prev => Math.max(0.1, Math.min(10, prev - e.deltaY * 0.01)));
        }
    };

    const handleDrop = (e: DragEvent, trackId: string) => {
        e.preventDefault();
        const data = e.dataTransfer.getData("application/json");
        if (!data) return;
        
        try {
            const asset = JSON.parse(data);
            const rect = (e.currentTarget as HTMLElement).getBoundingClientRect();
            const x = e.clientX - rect.left + (scrollRef.current?.scrollLeft || 0);
            const ms = x / pixelsPerMs;
            onDropAsset(trackId, asset, ms);
        } catch (err) {
            console.error("Drop failed", err);
        }
    };

    return (
        <div className="timeline-master" onWheel={onWheel}>
            <div className="timeline-toolbar">
                <span className="timeline-title">Master Timeline: {snapshot.show_id}</span>
                <div className="zoom-controls">
                    <button onClick={() => setZoom(z => Math.max(0.1, z - 0.2))}>-</button>
                    <span>{zoom.toFixed(1)}x</span>
                    <button onClick={() => setZoom(z => Math.min(10, z + 0.2))}>+</button>
                </div>
            </div>
            
            <div className="timeline-view-container" ref={scrollRef}>
                <div 
                    className="timeline-ruler" 
                    style={{ width: totalWidth, height: '24px', position: 'relative', background: 'var(--panel-3)' }}
                    onClick={handleTimelineClick}
                >
                    {/* Time ticks every 1s, 5s, 10s based on zoom */}
                    {Array.from({ length: Math.ceil(snapshot.duration_ms / 1000) }).map((_, i) => (
                        <div 
                            key={i} 
                            style={{ 
                                position: 'absolute', 
                                left: i * 1000 * pixelsPerMs, 
                                height: i % 5 === 0 ? '100%' : '50%',
                                borderLeft: '1px solid var(--muted)',
                                paddingLeft: '4px',
                                fontSize: '10px'
                            }}
                        >
                            {i % 5 === 0 ? `${i}s` : ''}
                        </div>
                    ))}
                </div>

                <div className="tracks-container" style={{ width: totalWidth, position: 'relative' }}>
                    {snapshot.tracks.map(track => (
                        <div 
                            key={track.track_id} 
                            className="timeline-track"
                            onDragOver={(e) => e.preventDefault()}
                            onDrop={(e) => handleDrop(e, track.track_id)}
                            style={{ 
                                height: '60px', 
                                borderBottom: '1px solid var(--line)', 
                                position: 'relative',
                                background: 'rgba(255,255,255,0.02)'
                            }}
                        >
                            <div className="track-label" style={{ 
                                position: 'sticky', 
                                left: 0, 
                                zIndex: 10, 
                                background: 'var(--panel-2)', 
                                width: '120px',
                                height: '100%',
                                display: 'flex',
                                alignItems: 'center',
                                padding: '0 8px',
                                fontSize: '11px',
                                fontWeight: 'bold'
                            }}>
                                {track.label}
                            </div>
                            
                            {track.clips.map(clip => (
                                <div 
                                    key={clip.clip_id}
                                    className={`timeline-clip clip-${clip.kind}`}
                                    style={{
                                        position: 'absolute',
                                        left: clip.start_ms * pixelsPerMs,
                                        width: clip.duration_ms * pixelsPerMs,
                                        height: '40px',
                                        top: '10px',
                                        background: 'var(--accent)',
                                        opacity: 0.8,
                                        borderRadius: '4px',
                                        padding: '4px',
                                        fontSize: '10px',
                                        overflow: 'hidden',
                                        border: '1px solid rgba(255,255,255,0.2)'
                                    }}
                                >
                                    {clip.label}
                                </div>
                            ))}
                        </div>
                    ))}

                    {/* Playhead */}
                    <div 
                        className="playhead" 
                        style={{ 
                            position: 'absolute', 
                            top: 0, 
                            bottom: 0, 
                            left: playheadPos, 
                            width: '2px', 
                            background: '#ff4444',
                            zIndex: 20,
                            pointerEvents: 'none'
                        }}
                    >
                        <div style={{ 
                            width: '12px', 
                            height: '12px', 
                            background: '#ff4444', 
                            borderRadius: '50%', 
                            marginLeft: '-5px', 
                            marginTop: '-6px' 
                        }} />
                    </div>
                </div>
            </div>
            
            <style jsx>{`
                .timeline-master {
                    display: flex;
                    flex-direction: column;
                    background: var(--panel-1);
                    border: 1px solid var(--line);
                    border-radius: 8px;
                    overflow: hidden;
                    height: 100%;
                }
                .timeline-toolbar {
                    display: flex;
                    justify-content: space-between;
                    align-items: center;
                    padding: 8px 12px;
                    background: var(--panel-2);
                    border-bottom: 1px solid var(--line);
                }
                .timeline-title {
                    font-size: 11px;
                    font-weight: bold;
                    text-transform: uppercase;
                    letter-spacing: 0.05em;
                }
                .zoom-controls {
                    display: flex;
                    align-items: center;
                    gap: 8px;
                    font-size: 11px;
                }
                .timeline-view-container {
                    flex: 1;
                    overflow: auto;
                    position: relative;
                }
                .timeline-clip.clip-video { background: #3b82f6; }
                .timeline-clip.clip-audio { background: #10b981; }
                .timeline-clip.clip-trigger { background: #f59e0b; }
                .timeline-clip.clip-alpha { background: #8b5cf6; }
            `}</style>
        </div>
    );
}
