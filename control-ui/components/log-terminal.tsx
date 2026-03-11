"use client";

import { useState, useEffect, useRef, useCallback } from 'react';

interface LogEntry {
    timestamp: string;
    level: string;
    event: string;
    message: string;
    detail: any;
}

export function LogTerminal() {
    const [logs, setLogs] = useState<LogEntry[]>([]);
    const [filter, setFilter] = useState('');
    const [levelFilter, setLevelFilter] = useState('ALL');
    const scrollRef = useRef<HTMLDivElement>(null);
    const [autoScroll, setAutoScroll] = useState(true);

    const wsUrl = process.env.NEXT_PUBLIC_ORCHESTRATION_WS_LOGS || "ws://localhost:8010/ws/logs";
    const apiUrl = process.env.NEXT_PUBLIC_ORCHESTRATION_HTTP || "http://localhost:8010";

    useEffect(() => {
        const ws = new WebSocket(wsUrl);
        ws.onmessage = (event) => {
            const entry = JSON.parse(event.data);
            setLogs(prev => [...prev.slice(-499), entry]); // Keep last 500
        };
        return () => ws.close();
    }, [wsUrl]);

    useEffect(() => {
        if (autoScroll && scrollRef.current) {
            scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
        }
    }, [logs, autoScroll]);

    const filteredLogs = logs.filter(log => {
        const matchesLevel = levelFilter === 'ALL' || log.level === levelFilter;
        const matchesSearch = !filter || 
            log.message.toLowerCase().includes(filter.toLowerCase()) || 
            log.event.toLowerCase().includes(filter.toLowerCase());
        return matchesLevel && matchesSearch;
    });

    const handleExport = () => {
        window.open(`${apiUrl}/api/v1/logs/export`, '_blank');
    };

    return (
        <div className="log-terminal">
            <div className="terminal-header">
                <div className="terminal-controls">
                    <span className="terminal-title">SHOW OPERATIONS LOG</span>
                    <select className="input compact" value={levelFilter} onChange={e => setLevelFilter(e.target.value)}>
                        <option value="ALL">All Levels</option>
                        <option value="INFO">Info</option>
                        <option value="WARN">Warning</option>
                        <option value="ERROR">Error</option>
                    </select>
                    <input 
                        className="input compact" 
                        placeholder="Filter log..." 
                        value={filter}
                        onChange={e => setFilter(e.target.value)}
                    />
                </div>
                <div className="terminal-actions">
                    <label className="checkbox-label">
                        <input type="checkbox" checked={autoScroll} onChange={e => setAutoScroll(e.target.checked)} />
                        Auto-scroll
                    </label>
                    <button className="btn subtle compact" onClick={() => setLogs([])}>Clear</button>
                    <button className="btn secondary compact" onClick={handleExport}>Export All</button>
                </div>
            </div>
            
            <div className="terminal-body" ref={scrollRef}>
                {filteredLogs.map((log, i) => (
                    <div key={i} className={`log-line level-${log.level.toLowerCase()}`}>
                        <span className="log-time">{log.timestamp.split('T')[1]}</span>
                        <span className="log-level">[{log.level}]</span>
                        <span className="log-event">{log.event}</span>
                        <span className="log-msg">{log.message}</span>
                    </div>
                ))}
                {filteredLogs.length === 0 && <div className="muted empty-msg">No logs matching filters.</div>}
            </div>

            <style jsx>{`
                .log-terminal {
                    display: flex;
                    flex-direction: column;
                    background: #000;
                    color: #fff;
                    font-family: 'DM Mono', monospace;
                    font-size: 11px;
                    height: 100%;
                    border: 1px solid var(--line);
                    border-radius: 4px;
                }
                .terminal-header {
                    display: flex;
                    justify-content: space-between;
                    padding: 4px 8px;
                    background: #111;
                    border-bottom: 1px solid #333;
                }
                .terminal-controls, .terminal-actions {
                    display: flex;
                    align-items: center;
                    gap: 8px;
                }
                .terminal-title {
                    color: var(--muted);
                    font-weight: bold;
                    margin-right: 8px;
                }
                .terminal-body {
                    flex: 1;
                    overflow-y: auto;
                    padding: 8px;
                    line-height: 1.4;
                }
                .log-line {
                    display: flex;
                    gap: 8px;
                    margin-bottom: 2px;
                    white-space: pre-wrap;
                }
                .log-time { color: #888; }
                .log-level { font-weight: bold; width: 60px; }
                .log-event { color: var(--accent); width: 100px; }
                .level-info .log-level { color: #4ade80; }
                .level-warn .log-level { color: #facc15; }
                .level-error .log-level { color: #f87171; }
                .empty-msg { text-align: center; padding: 20px; }
                .checkbox-label { font-size: 10px; display: flex; align-items: center; gap: 4px; }
            `}</style>
        </div>
    );
}
