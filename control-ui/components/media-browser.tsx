"use client";

import { useState, useEffect, useCallback } from 'react';
import { auth } from '../lib/auth';
import { BrowserEntry, BrowserListResponse, MediaAsset } from '../lib/types';

interface MediaBrowserProps {
    onAssetIngested?: (asset: MediaAsset) => void;
}

export function MediaBrowser({ onAssetIngested }: MediaBrowserProps) {
    const [currentPath, setCurrentPath] = useState<string>("");
    const [entries, setEntries] = useState<BrowserEntry[]>([]);
    const [parentPath, setParentPath] = useState<string | null>(null);
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState<string | null>(null);
    const [search, setSearch] = useState("");

    const API_URL = process.env.NEXT_PUBLIC_ORCHESTRATION_HTTP || "http://localhost:8010";

    const loadDirectory = useCallback(async (path: string = "") => {
        setLoading(true);
        setError(null);
        try {
            const res = await auth.fetch(`${API_URL}/api/v1/browser/list?path=${encodeURIComponent(path)}`);
            if (!res.ok) throw new Error(`Failed to load directory: ${res.statusText}`);
            const data: BrowserListResponse = await res.json();
            setCurrentPath(data.path);
            setParentPath(data.parent);
            setEntries(data.entries);
        } catch (err) {
            setError(err instanceof Error ? err.message : "Unknown error");
        } finally {
            setLoading(false);
        }
    }, [API_URL]);

    useEffect(() => {
        loadDirectory();
    }, [loadDirectory]);

    const handleIngest = async (entry: BrowserEntry) => {
        try {
            const res = await auth.fetch(`${API_URL}/api/v1/media/ingest_local?path=${encodeURIComponent(entry.path)}`, {
                method: 'POST'
            });
            if (!res.ok) throw new Error("Ingest failed");
            const data = await res.json();
            if (onAssetIngested && data.asset) {
                onAssetIngested(data.asset);
            }
            alert(`Ingested ${entry.name} successfully!`);
        } catch (err) {
            alert(`Error ingesting file: ${err instanceof Error ? err.message : "Unknown error"}`);
        }
    };

    const filteredEntries = entries.filter(e => 
        e.name.toLowerCase().includes(search.toLowerCase())
    );

    return (
        <div className="media-browser" style={{ display: 'flex', flexDirection: 'column', height: '100%', gap: '10px' }}>
            <div className="browser-header" style={{ display: 'flex', gap: '8px', alignItems: 'center' }}>
                <button 
                    className="btn compact" 
                    onClick={() => parentPath && loadDirectory(parentPath)}
                    disabled={!parentPath || loading}
                >
                    ↑ Up
                </button>
                <div style={{ flex: 1, fontSize: '11px', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', opacity: 0.7 }}>
                    {currentPath}
                </div>
                <input 
                    className="input compact" 
                    placeholder="Filter..." 
                    value={search}
                    onChange={(e) => setSearch(e.target.value)}
                    style={{ width: '100px' }}
                />
            </div>

            <div className="browser-list" style={{ flex: 1, overflowY: 'auto', border: '1px solid var(--line)', background: 'var(--panel-2)' }}>
                {loading && <div style={{ padding: '20px', textAlign: 'center' }}>Loading...</div>}
                {!loading && filteredEntries.length === 0 && <div style={{ padding: '20px', textAlign: 'center', opacity: 0.5 }}>No items found</div>}
                
                {filteredEntries.map(entry => (
                    <div 
                        key={entry.path} 
                        className="browser-entry"
                        style={{ 
                            display: 'flex', 
                            justifyContent: 'space-between', 
                            padding: '6px 8px', 
                            borderBottom: '1px solid var(--line)',
                            cursor: entry.is_dir ? 'pointer' : 'default',
                            alignItems: 'center'
                        }}
                        onClick={() => entry.is_dir && loadDirectory(entry.path)}
                    >
                        <div style={{ display: 'flex', gap: '8px', alignItems: 'center', flex: 1, overflow: 'hidden' }}>
                            <span style={{ fontSize: '14px' }}>{entry.is_dir ? '📁' : '📄'}</span>
                            <span style={{ fontSize: '12px', fontWeight: entry.is_dir ? 'bold' : 'normal', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                                {entry.name}
                            </span>
                        </div>
                        {!entry.is_dir && (
                            <button 
                                className="btn compact" 
                                style={{ padding: '2px 6px', fontSize: '10px' }}
                                onClick={(e) => { e.stopPropagation(); handleIngest(entry); }}
                            >
                                + Add
                            </button>
                        )}
                    </div>
                ))}
            </div>
            {error && <div style={{ color: 'var(--error)', fontSize: '11px' }}>{error}</div>}
        </div>
    );
}
