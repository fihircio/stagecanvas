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

  const onConnect = useCallback(
    (params:Edge | Connection) => setEdges((eds) => addEdge(params, eds)),
    [setEdges]
  );

  return (
    <div style={{ width: '100%', height: '100%' }}>
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
