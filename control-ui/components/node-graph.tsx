"use client";

import React, { useState, useCallback, useEffect } from 'react';
import ReactFlow, {
  MiniMap,
  Controls,
  Background,
  useNodesState,
  useEdgesState,
  addEdge,
  Connection,
  Edge,
  Handle,
  Position,
  NodeProps,
} from 'reactflow';
import 'reactflow/dist/style.css';
import { compileGraphToRules } from '../lib/compiler';
import { useLocks } from '../hooks/use-locks';

// Custom Nodes
const CameraInputNode = ({ data }: NodeProps) => {
  return (
    <div style={{ background: '#333', color: '#fff', padding: '10px', borderRadius: '5px', border: '1px solid #555' }}>
      <Handle type="source" position={Position.Right} id="out" />
      <div>📷 {data.label}</div>
    </div>
  );
};

const YoloTriggerNode = ({ data }: NodeProps) => {
  return (
    <div style={{ background: '#0055aa', color: '#fff', padding: '10px', borderRadius: '5px', border: '1px solid #0077ff' }}>
      <Handle type="target" position={Position.Left} id="in" />
      <Handle type="source" position={Position.Right} id="out" />
      <div>🎯 {data.label}</div>
    </div>
  );
};

const PlayClipNode = ({ data }: NodeProps) => {
  return (
    <div style={{ background: '#00aa55', color: '#fff', padding: '10px', borderRadius: '5px', border: '1px solid #00ff77' }}>
      <Handle type="target" position={Position.Left} id="in" />
      <div>▶️ {data.label}</div>
    </div>
  );
};

const TimerNode = ({ data }: NodeProps) => {
  return (
    <div style={{ background: '#7700aa', color: '#fff', padding: '10px', borderRadius: '5px', border: '1px solid #9900ff' }}>
      <Handle type="target" position={Position.Left} id="in" />
      <Handle type="source" position={Position.Right} id="out" />
      <div>⏳ {data.label}</div>
      <div style={{ fontSize: '10px', opacity: 0.8 }}>Delay: {data.delay_ms || 1000}ms</div>
    </div>
  );
};

const CounterNode = ({ data }: NodeProps) => {
  return (
    <div style={{ background: '#aa5500', color: '#fff', padding: '10px', borderRadius: '5px', border: '1px solid #ff7700' }}>
      <Handle type="target" position={Position.Left} id="in" />
      <Handle type="source" position={Position.Right} id="out" />
      <div>🔢 {data.label}</div>
      <div style={{ fontSize: '10px', opacity: 0.8 }}>Hits: {data.counter_target || 3}</div>
    </div>
  );
};

const LogicNode = ({ data }: NodeProps) => {
  return (
    <div style={{ background: '#aa0000', color: '#fff', padding: '10px', borderRadius: '5px', border: '1px solid #ff0000' }}>
      <Handle type="target" position={Position.Left} id="in" />
      <Handle type="source" position={Position.Right} id="out" />
      <div>⚖️ {data.label}</div>
      <div style={{ fontSize: '10px', opacity: 0.8 }}>If: {data.condition || 'payload.value > 0.5'}</div>
    </div>
  );
};

const nodeTypes = {
  cameraInput: CameraInputNode,
  yoloTrigger: YoloTriggerNode,
  playClip: PlayClipNode,
  timer: TimerNode,
  counter: CounterNode,
  logic: LogicNode,
};

const initialNodes: any[] = [
  { id: '1', type: 'cameraInput', position: { x: 50, y: 150 }, data: { label: 'Camera M1' } },
  { id: '2', type: 'yoloTrigger', position: { x: 300, y: 150 }, data: { label: 'Detect: Person' } },
  { id: '3', type: 'timer', position: { x: 550, y: 50 }, data: { label: 'Intro Delay', delay_ms: 2000 } },
  { id: '4', type: 'counter', position: { x: 550, y: 250 }, data: { label: 'Gate Count', counter_target: 5 } },
  { id: '5', type: 'playClip', position: { x: 800, y: 150 }, data: { label: 'Play Clip: show2' } },
];

const initialEdges = [
  { id: 'e1-2', source: '1', target: '2', animated: true },
  { id: 'e2-3', source: '2', target: '3' },
  { id: 'e2-4', source: '2', target: '4' },
  { id: 'e3-5', source: '3', target: '5' },
  { id: 'e4-5', source: '4', target: '5' },
];

const DEFAULT_USER_ID = `operator-${Math.random().toString(36).slice(2, 7)}`;

export function NodeGraph() {
  const [nodes, setNodes, onNodesChange] = useNodesState(initialNodes);
  const [edges, setEdges, onEdgesChange] = useEdgesState(initialEdges);
  const [deployStatus, setDeployStatus] = useState<string | null>(null);
  const { locks, takeControl, releaseControl, isLockedByOther } = useLocks();
  const [userId, setUserId] = useState<string>('');

  useEffect(() => {
    const stored = localStorage.getItem('sc-user-id') || DEFAULT_USER_ID;
    setUserId(stored);
    localStorage.setItem('sc-user-id', stored);
  }, []);

  const resourceId = 'node-graph-main';
  const isLocked = isLockedByOther(resourceId);
  const hasControl = locks[resourceId]?.user_id === userId;

  const onConnect = useCallback(
    (params: Edge | Connection) => setEdges((eds) => addEdge(params, eds)),
    [setEdges]
  );

  const toggleControl = async () => {
    if (hasControl) {
      await releaseControl(resourceId, userId);
    } else {
      await takeControl(resourceId, userId);
    }
  };

  const handleDeploy = async () => {
    if (isLocked) return;
    setDeployStatus("Deploying...");
    try {
      const rules = compileGraphToRules(nodes, edges);

      for (const rule of rules) {
        const response = await fetch(`${process.env.NEXT_PUBLIC_ORCHESTRATION_HTTP || 'http://localhost:18010'}/api/v1/triggers/register`, {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
          },
          body: JSON.stringify(rule),
        });

        if (!response.ok) {
          throw new Error(`Failed to deploy rule: ${rule.rule_id}`);
        }
      }
      setDeployStatus("Success!");
      setTimeout(() => setDeployStatus(null), 3000);
    } catch (err: any) {
      setDeployStatus(`Error: ${err.message}`);
      setTimeout(() => setDeployStatus(null), 5000);
    }
  };

  return (
    <div style={{ width: '100%', height: '100%', position: 'relative' }}>
      <div style={{
        position: 'absolute',
        top: 20,
        right: 20,
        zIndex: 10,
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'flex-end',
        gap: '10px'
      }}>
        <button
          onClick={handleDeploy}
          style={{
            padding: '12px 24px',
            background: '#0070f3',
            color: 'white',
            border: 'none',
            borderRadius: '6px',
            fontSize: '16px',
            fontWeight: '600',
            boxShadow: '0 4px 6px rgba(0,0,0,0.1)',
            cursor: 'pointer',
            transition: 'transform 0.2s, background 0.2s',
          }}
          onMouseEnter={(e) => e.currentTarget.style.background = '#0060d3'}
          onMouseLeave={(e) => e.currentTarget.style.background = '#0070f3'}
          onMouseDown={(e) => e.currentTarget.style.transform = 'scale(0.95)'}
          onMouseUp={(e) => e.currentTarget.style.transform = 'scale(1)'}
          disabled={isLocked || !hasControl}
        >
          {isLocked ? '🔒 Locked' : hasControl ? '🚀 Deploy Rules' : '⚠️ Need Control'}
        </button>
        <button
          onClick={toggleControl}
          style={{
            padding: '8px 16px',
            background: hasControl ? '#aa0000' : '#00aa55',
            color: 'white',
            border: 'none',
            borderRadius: '4px',
            fontSize: '14px',
            fontWeight: '600',
            cursor: 'pointer',
          }}
        >
          {hasControl ? 'Release Control' : 'Take Control'}
        </button>
        {isLocked && !hasControl && (
          <div style={{ color: '#ff4444', fontSize: '12px', fontWeight: 'bold' }}>
            Locked by: {locks[resourceId]?.user_id}
          </div>
        )}
        {deployStatus && (
          <div style={{
            background: deployStatus.includes('Error') ? '#ff4444' : '#00aa55',
            color: 'white',
            padding: '8px 16px',
            borderRadius: '4px',
            fontSize: '14px'
          }}>
            {deployStatus}
          </div>
        )}
      </div>
      <ReactFlow
        nodes={nodes}
        edges={edges}
        onNodesChange={onNodesChange}
        onEdgesChange={onEdgesChange}
        onConnect={onConnect}
        nodeTypes={nodeTypes}
        fitView
        attributionPosition="bottom-right"
      >
        <Controls />
        <MiniMap />
        <Background gap={12} size={1} />
      </ReactFlow>
    </div>
  );
}
