import { NodeGraph } from '../../components/node-graph';

export default function DesignerPage() {
    return (
        <div style={{ width: '100vw', height: '100vh', display: 'flex', flexDirection: 'column' }}>
            <header style={{ padding: '10px 20px', background: '#111', color: '#fff', borderBottom: '1px solid #333' }}>
                <h1 style={{ fontSize: '1.2rem', margin: 0 }}>StageCanvas Designer (Phase 1 USP)</h1>
            </header>
            <main style={{ flex: 1, backgroundColor: '#0a0a0a' }}>
                <NodeGraph />
            </main>
        </div>
    );
}
