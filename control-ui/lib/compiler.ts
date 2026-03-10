import { Node, Edge } from 'reactflow';

export interface TriggerRegisterRequest {
    rule_id: string;
    name?: string;
    source: "osc" | "http";
    cue_id?: string;
    payload: Record<string, any>;
}

/**
 * Compiles the visual node-graph into a set of trigger rules for the Orchestrator.
 * Currently supports mapping YOLO Trigger -> Play Clip.
 */
export function compileGraphToRules(nodes: Node[], edges: Edge[]): TriggerRegisterRequest[] {
    const rules: TriggerRegisterRequest[] = [];

    // Find all playClip nodes as they represent the ACTION
    const playClipNodes = nodes.filter(n => n.type === 'playClip');

    playClipNodes.forEach(clipNode => {
        // Find edges pointing TO this clip node
        const incomingEdges = edges.filter(e => e.target === clipNode.id);

        incomingEdges.forEach(edge => {
            const sourceNode = nodes.find(n => n.id === edge.source);

            if (sourceNode?.type === 'yoloTrigger') {
                // We found a connection: YOLO -> Play Clip
                // Extract clip name from label: "Play Clip: <show_id>"
                const clipMatch = clipNode.data.label.match(/Play Clip:\s*(.+)/i);
                const clipId = clipMatch ? clipMatch[1].trim() : 'unknown';

                // Extract trigger ID from label: "Detect: <id>"
                const triggerMatch = sourceNode.data.label.match(/Detect:\s*(.+)/i);
                const triggerId = triggerMatch ? triggerMatch[1].trim() : sourceNode.id;

                rules.push({
                    rule_id: `yolo-${triggerId}`,
                    name: `Auto-generated from Graph: ${sourceNode.data.label} -> ${clipNode.data.label}`,
                    source: "osc", // YOLO usually sends via OSC
                    payload: {
                        command: "PLAY_SHOW",
                        show_id: clipId,
                        origin: "node-graph-compiler"
                    }
                });
            }
        });
    });

    return rules;
}
