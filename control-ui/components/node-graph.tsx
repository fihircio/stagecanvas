"use client";

import React, { useState, useCallback } from 'react';
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

const nodeTypes = {
  cameraInput: CameraInputNode,
  yoloTrigger: YoloTriggerNode,
  playClip: PlayClipNode,
};

const initialNodes = [
  { id: '1', type: 'cameraInput', position: { x: 50, y: 150 }, data: { label: 'Camera M1' } },
  { id: '2', type: 'yoloTrigger', position: { x: 300, y: 150 }, data: { label: 'Detect: Person' } },
  { id: '3', type: 'playClip', position: { x: 600, y: 150 }, data: { label: 'Play Clip: show2' } },
];

const initialEdges = [
  { id: 'e1-2', source: '1', target: '2', animated: true },
  { id: 'e2-3', source: '2', target: '3' },
];

export function NodeGraph() {
  const [nodes, setNodes, onNodesChange] = useNodesState(initialNodes);
  const [edges, setEdges, onEdgesChange] = useEdgesState(initialEdges);
  const [deployStatus, setDeployStatus] = useState<string | null>(null);

  const onConnect = useCallback(
    (params: Edge | Connection) => setEdges((eds) => addEdge(params, eds)),
    [setEdges]
  );

  const handleDeploy = async () => {
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
        >
          🚀 Deploy Rules
        </button>
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
