import { Node, Edge } from 'reactflow';

export interface LogicConfig {
    delay_ms?: number;
    counter_target?: number;
    condition?: string;
}

export interface TriggerRegisterRequest {
    rule_id: string;
    name?: string;
    source: "osc" | "http" | "midi";
    cue_id?: string;
    payload: Record<string, any>;
    logic?: LogicConfig;
}

/**
 * Compiles the visual node-graph into a set of trigger rules for the Orchestrator.
 * Aggregates logic nodes (Timer, Counter, Logic) in the path between source and action.
 */
export function compileGraphToRules(nodes: Node[], edges: Edge[]): TriggerRegisterRequest[] {
    const rules: TriggerRegisterRequest[] = [];

    // Find all playClip nodes as they represent the ACTION
    const playClipNodes = nodes.filter(n => n.type === 'playClip');

    playClipNodes.forEach(clipNode => {
        // Trace back from the clip node to find the source and any logic nodes in between
        const findSources = (targetId: string, currentLogic: LogicConfig = {}): { source: Node, logic: LogicConfig }[] => {
            const incomingEdges = edges.filter(e => e.target === targetId);
            let results: { source: Node, logic: LogicConfig }[] = [];

            incomingEdges.forEach(edge => {
                const node = nodes.find(n => n.id === edge.source);
                if (!node) return;

                // Merge node-specific logic
                const nextLogic = { ...currentLogic };
                if (node.type === 'timer') nextLogic.delay_ms = (nextLogic.delay_ms || 0) + (node.data.delay_ms || 1000);
                if (node.type === 'counter') nextLogic.counter_target = node.data.counter_target || 3;
                if (node.type === 'logic') nextLogic.condition = node.data.condition || 'payload.value > 0.5';

                if (node.type === 'yoloTrigger' || node.type === 'cameraInput') {
                    results.push({ source: node, logic: nextLogic });
                } else {
                    // It's a logic node, keep tracing back
                    results = [...results, ...findSources(node.id, nextLogic)];
                }
            });
            return results;
        };

        const sources = findSources(clipNode.id);

        sources.forEach(({ source, logic }) => {
            // Extract clip name from label
            const clipMatch = clipNode.data.label.match(/Play Clip:\s*(.+)/i);
            const clipId = clipMatch ? clipMatch[1].trim() : 'unknown';

            // Extract trigger ID from source node
            const triggerMatch = source.data.label.match(/Detect:\s*(.+)/i);
            const triggerId = triggerMatch ? triggerMatch[1].trim() : source.id;

            rules.push({
                rule_id: `rule-${triggerId}-${clipId}`,
                name: `Graph: ${source.data.label} -> ${clipNode.data.label}`,
                source: "osc",
                payload: {
                    command: "PLAY_SHOW",
                    show_id: clipId,
                    origin: "node-graph-compiler"
                },
                logic: Object.keys(logic).length > 0 ? logic : undefined
            });
        });
    });

    return rules;
}
