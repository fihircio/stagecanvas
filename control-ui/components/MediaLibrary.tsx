"use client";

import { useState, useEffect, useCallback } from 'react';
import { auth } from '../lib/auth';
import { MediaAsset } from '../lib/types';

export function MediaLibrary() {
    const [assets, setAssets] = useState<MediaAsset[]>([]);
    const [loading, setLoading] = useState(false);
    const [isDragging, setIsDragging] = useState(false);

    const API_URL = process.env.NEXT_PUBLIC_ORCHESTRATION_HTTP || "http://localhost:8010";

    const loadAssets = useCallback(async () => {
        setLoading(true);
        try {
            const res = await auth.fetch(`${API_URL}/api/v1/media`);
            if (!res.ok) throw new Error("Failed to load assets");
            const data = await res.json();
            setAssets(data.assets || []);
        } catch (err) {
            console.error(err);
        } finally {
            setLoading(false);
        }
    }, [API_URL]);

    useEffect(() => {
        loadAssets();
    }, [loadAssets]);

    const handleFileUpload = async (file: File) => {
        const formData = new FormData();
        const assetId = `asset-${Date.now()}`;
        formData.append('file', file);
        formData.append('asset_id', assetId);
        formData.append('codec_profile', 'generic'); // Stub for now
        formData.append('label', file.name);

        try {
            const res = await auth.fetch(`${API_URL}/api/v1/media/upload`, {
                method: 'POST',
                body: formData,
                headers: {
                    // Content-Type is handled automatically by FETCH when using FormData
                    'Content-Type': 'multipart/form-data', 
                }
            });
            // Fix: remove Content-Type to let browser set it with boundary
            const res2 = await auth.fetch(`${API_URL}/api/v1/media/upload`, {
                method: 'POST',
                body: formData,
                headers: { 'Accept': 'application/json' } // Don't set Content-Type
            });

            if (!res2.ok) throw new Error("Upload failed");
            await loadAssets();
        } catch (err) {
            alert(`Upload error: ${err instanceof Error ? err.message : "Unknown error"}`);
        }
    };

    const onDrop = (e: React.DragEvent) => {
        e.preventDefault();
        setIsDragging(false);
        if (e.dataTransfer.files && e.dataTransfer.files.length > 0) {
            Array.from(e.dataTransfer.files).forEach(file => handleFileUpload(file));
        }
    };

    return (
        <div className="media-library" style={{ display: 'flex', flexDirection: 'column', height: '100%' }}>
            <div 
                className={`drop-zone ${isDragging ? 'active' : ''}`}
                onDragOver={(e) => { e.preventDefault(); setIsDragging(true); }}
                onDragLeave={() => setIsDragging(false)}
                onDrop={onDrop}
                style={{
                    border: '2px dashed var(--line)',
                    borderRadius: '8px',
                    padding: '20px',
                    textAlign: 'center',
                    marginBottom: '16px',
                    background: isDragging ? 'rgba(var(--ok), 0.1)' : 'transparent',
                    transition: 'all 0.2s',
                    fontSize: '13px',
                    color: 'var(--muted)'
                }}
            >
                {isDragging ? 'Drop to Ingest Media' : 'Drag & Drop Media Files Here'}
            </div>

            <div className="asset-grid" style={{ 
                display: 'grid', 
                gridTemplateColumns: 'repeat(auto-fill, minmax(140px, 1fr))', 
                gap: '12px',
                overflowY: 'auto',
                flex: 1
            }}>
                {loading && assets.length === 0 && <div style={{ textAlign: 'center', padding: '20px' }}>Loading assets...</div>}
                
                {assets.map(asset => (
                    <div 
                        key={asset.asset_id} 
                        className="asset-card" 
                        style={{ 
                            background: 'var(--panel-2)', 
                            border: '1px solid var(--line)',
                            borderRadius: '4px',
                            overflow: 'hidden',
                            display: 'flex',
                            flexDirection: 'column'
                        }}
                    >
                        <div className="thumbnail-wrapper" style={{ 
                            width: '100%', 
                            aspectRatio: '16/9', 
                            background: '#000',
                            position: 'relative',
                            overflow: 'hidden'
                        }}>
                            <img 
                                src={`${API_URL}/api/v1/media/thumbnails/${asset.asset_id}`} 
                                alt={asset.label}
                                style={{ width: '100%', height: '100%', objectFit: 'cover' }}
                                onError={(e) => { (e.target as HTMLImageElement).src = 'https://placehold.co/320x180/111/444?text=No+Thumb'; }}
                            />
                            <div style={{ 
                                position: 'absolute', 
                                bottom: '4px', 
                                right: '4px', 
                                background: 'rgba(0,0,0,0.7)', 
                                color: '#fff', 
                                fontSize: '10px', 
                                padding: '1px 4px',
                                borderRadius: '2px'
                            }}>
                                {(asset.duration_ms / 1000).toFixed(1)}s
                            </div>
                        </div>
                        <div style={{ padding: '8px', flex: 1 }}>
                            <div style={{ fontSize: '12px', fontWeight: 'bold', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', marginBottom: '4px' }}>
                                {asset.label}
                            </div>
                            <div style={{ fontSize: '10px', color: 'var(--muted)', display: 'grid', gap: '2px' }}>
                                <span>{asset.metadata?.codec || asset.codec_profile}</span>
                                <span>{asset.metadata?.width}x{asset.metadata?.height} @ {asset.metadata?.fps}fps</span>
                            </div>
                        </div>
                    </div>
                ))}
            </div>
        </div>
    );
}
