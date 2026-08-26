import { useCallback, useEffect, useMemo, useRef } from 'react';
import ForceGraph2D, { type ForceGraphMethods } from 'react-force-graph-2d';
import type { Edge, Neuron } from '../api/types';
import type { MaterialisedFrame } from '../api/protocol';
import {
  activationColor,
  nodeRadius,
  polarityColor,
  polarityOfSign,
  tracePolarityShape,
} from './encoding';
import { computeLayout, type GroupArc, type LayoutId } from './layouts';

/**
 * Canvas renderer for the circuit.
 *
 * **Why canvas and not SVG.** 153 nodes is nothing, but 2 695 edges is not:
 * as SVG that is 2 695 live DOM nodes whose `stroke` would have to be
 * reassigned on every animation frame, which is exactly the workload that makes
 * naive graph views stutter. `react-force-graph-2d` draws the whole scene into
 * a single `<canvas>` with a 2D context, so a frame costs ~2 850 draw calls and
 * zero DOM mutations, and it comes with pan, zoom and pointer picking already
 * solved. WebGL (sigma.js) would also work and would scale further, but at this
 * size it buys nothing and costs a much less flexible custom-drawing API — and
 * per-node custom drawing is what the polarity glyphs need.
 *
 * **Why the hot data goes through refs.** The activation vector changes on
 * every playback tick. Keeping it in refs means the draw callbacks keep a
 * stable identity and the graph engine is never handed "new" accessor props, so
 * the animation never restarts the layout or rebuilds internal caches.
 */

export interface GraphNode {
  /** FlyWire root id, kept as an opaque string. Never parsed as a number. */
  id: string;
  index: number;
  neuron: Neuron;
  radius: number;
  x?: number;
  y?: number;
  fx?: number;
  fy?: number;
}

export interface GraphLink {
  source: string | GraphNode;
  target: string | GraphNode;
  preIndex: number;
  postIndex: number;
  synCount: number;
  sign: number;
  width: number;
}

export interface GraphViewProps {
  neurons: Neuron[];
  edges: Edge[];
  cellTypeOrder: string[];
  layout: LayoutId;
  width: number;
  height: number;
  /** Current playback frame, or null before a run has produced one. */
  frame: MaterialisedFrame | null;
  /** Indices of the neurons the stimulus was injected into. */
  stimulatedIndices: Set<number>;
  /** Root id of the neuron shown in the inspector. */
  selectedRootId: string | null;
  /** Cell type highlighted from the legend; everything else is dimmed. */
  highlightedCellType: string | null;
  /** Hide connections with fewer synapses than this. */
  minSynapses: number;
  showEdges: boolean;
  onSelectNeuron: (rootId: string | null) => void;
}

/**
 * Resting edges are drawn very faint on purpose. Even after the synapse-count
 * filter there are hundreds of chords crossing the ring, and at any alpha where
 * a single edge is comfortably readable the overlap saturates into a solid
 * disc that hides the nodes — which are the thing that actually animates.
 */
const DIM_EDGE_ALPHA = 0.022;
const ACTIVE_EDGE_ALPHA = 0.8;

export function GraphView(props: GraphViewProps) {
  const {
    neurons,
    edges,
    cellTypeOrder,
    layout,
    width,
    height,
    frame,
    stimulatedIndices,
    selectedRootId,
    highlightedCellType,
    minSynapses,
    showEdges,
    onSelectNeuron,
  } = props;

  const fgRef = useRef<ForceGraphMethods<GraphNode, GraphLink> | undefined>(undefined);

  // ---- hot state, read by the draw callbacks without re-creating them ----
  const frameRef = useRef<MaterialisedFrame | null>(frame);
  frameRef.current = frame;
  const stimulatedRef = useRef(stimulatedIndices);
  stimulatedRef.current = stimulatedIndices;
  const selectedRef = useRef(selectedRootId);
  selectedRef.current = selectedRootId;
  const highlightRef = useRef(highlightedCellType);
  highlightRef.current = highlightedCellType;
  const minSynRef = useRef(minSynapses);
  minSynRef.current = minSynapses;
  const hoverRef = useRef<string | null>(null);
  const neighboursRef = useRef<Set<number>>(new Set());

  // Built once per dataset. The engine mutates these objects (x, y, fx, fy), so
  // their identity has to survive re-renders.
  const graphData = useMemo(() => {
    const totals = neurons.map((n) => n.in_synapses + n.out_synapses);
    const minSyn = totals.length ? Math.min(...totals) : 0;
    const maxSyn = totals.length ? Math.max(...totals) : 1;
    const nodes: GraphNode[] = neurons.map((neuron) => ({
      id: neuron.root_id,
      index: neuron.index,
      neuron,
      radius: nodeRadius(neuron.in_synapses + neuron.out_synapses, minSyn, maxSyn),
    }));
    const maxSynCount = edges.reduce((acc, e) => Math.max(acc, e.syn_count), 1);
    const links: GraphLink[] = edges.map((edge) => ({
      source: edge.pre_root_id,
      target: edge.post_root_id,
      preIndex: edge.pre_index,
      postIndex: edge.post_index,
      synCount: edge.syn_count,
      sign: edge.sign,
      // Log width: a handful of connections carry hundreds of synapses and
      // would otherwise be opaque slabs across the view.
      width: 0.25 + 1.35 * (Math.log1p(edge.syn_count) / Math.log1p(maxSynCount)),
    }));
    return { nodes, links };
  }, [neurons, edges]);

  const nodeByIndex = useMemo(() => {
    const map = new Map<number, GraphNode>();
    for (const node of graphData.nodes) map.set(node.index, node);
    return map;
  }, [graphData]);

  const adjacency = useMemo(() => {
    const map = new Map<number, Set<number>>();
    for (const edge of edges) {
      if (!map.has(edge.pre_index)) map.set(edge.pre_index, new Set());
      if (!map.has(edge.post_index)) map.set(edge.post_index, new Set());
      map.get(edge.pre_index)!.add(edge.post_index);
      map.get(edge.post_index)!.add(edge.pre_index);
    }
    return map;
  }, [edges]);

  const groupsRef = useRef<GroupArc[]>([]);

  // ---- layout ----
  useEffect(() => {
    const result = computeLayout(layout, neurons, cellTypeOrder);
    groupsRef.current = result?.groups ?? [];

    if (result) {
      for (const node of graphData.nodes) {
        const point = result.positions[node.index];
        if (!point) continue;
        node.x = point.x;
        node.y = point.y;
        node.fx = point.x;
        node.fy = point.y;
      }
    } else {
      // Force layout: release the pins and let the engine settle.
      for (const node of graphData.nodes) {
        node.fx = undefined;
        node.fy = undefined;
      }
      fgRef.current?.d3ReheatSimulation();
    }

    // Padding leaves room for the group labels drawn outside the ring.
    const timer = window.setTimeout(
      () => fgRef.current?.zoomToFit(420, layout === 'ring' ? 155 : 60),
      layout === 'force' ? 900 : 60,
    );
    return () => window.clearTimeout(timer);
  }, [layout, neurons, cellTypeOrder, graphData]);

  // ---- draw callbacks (stable identity) ----
  const paintNode = useCallback(
    (node: GraphNode, ctx: CanvasRenderingContext2D, globalScale: number) => {
      if (node.x === undefined || node.y === undefined) return;
      const current = frameRef.current;
      const activation = current ? current.activation[node.index] ?? 0 : 0;
      const spiked = current ? current.spiked[node.index] === 1 : false;
      const stimulated = stimulatedRef.current.has(node.index);
      const polarity = polarityOfSign(node.neuron.sign);

      const highlight = highlightRef.current;
      const hovered = hoverRef.current;
      const dimmed =
        (highlight !== null && node.neuron.cell_type !== highlight) ||
        (hovered !== null &&
          hovered !== node.id &&
          !neighboursRef.current.has(node.index));

      ctx.save();
      if (dimmed) ctx.globalAlpha = 0.16;

      const r = node.radius;

      // Spike halo, drawn under the glyph so it reads as emission.
      if (spiked && !dimmed) {
        ctx.beginPath();
        ctx.arc(node.x, node.y, r + 5.5, 0, Math.PI * 2);
        ctx.fillStyle = 'rgba(255, 236, 178, 0.22)';
        ctx.fill();
      }

      tracePolarityShape(ctx, polarity, node.x, node.y, r);
      ctx.fillStyle = activationColor(activation);
      ctx.fill();
      ctx.lineWidth = Math.max(0.6, 1 / globalScale);
      ctx.strokeStyle = spiked ? '#fff4d6' : 'rgba(180, 196, 224, 0.55)';
      if (spiked) ctx.lineWidth = Math.max(1.4, 2 / globalScale);
      ctx.stroke();

      // Stimulus sources keep a dashed ring for the whole run, so "where did
      // this start" is answerable at any step, not just at step 1.
      if (stimulated) {
        ctx.beginPath();
        ctx.arc(node.x, node.y, r + 3.4, 0, Math.PI * 2);
        ctx.setLineDash([2.4, 2.2]);
        ctx.lineWidth = Math.max(0.9, 1.3 / globalScale);
        ctx.strokeStyle = '#7dd8ff';
        ctx.stroke();
        ctx.setLineDash([]);
      }

      if (selectedRef.current === node.id) {
        ctx.beginPath();
        ctx.arc(node.x, node.y, r + 7, 0, Math.PI * 2);
        ctx.lineWidth = Math.max(1.1, 1.6 / globalScale);
        ctx.strokeStyle = '#ffffff';
        ctx.stroke();
      }

      ctx.restore();
    },
    [],
  );

  const paintPointerArea = useCallback(
    (node: GraphNode, color: string, ctx: CanvasRenderingContext2D) => {
      if (node.x === undefined || node.y === undefined) return;
      ctx.fillStyle = color;
      ctx.beginPath();
      // Generous hit target: the glyphs are small at default zoom.
      ctx.arc(node.x, node.y, node.radius + 4, 0, Math.PI * 2);
      ctx.fill();
    },
    [],
  );

  const linkColor = useCallback((link: GraphLink) => {
    if (link.synCount < minSynRef.current) return 'rgba(0,0,0,0)';

    const highlight = highlightRef.current;
    if (highlight !== null) {
      const pre = nodeByIndex.get(link.preIndex)?.neuron.cell_type;
      const post = nodeByIndex.get(link.postIndex)?.neuron.cell_type;
      if (pre !== highlight && post !== highlight) return 'rgba(0,0,0,0)';
    }

    const hovered = hoverRef.current;
    if (hovered !== null) {
      const touchesHover =
        nodeByIndex.get(link.preIndex)?.id === hovered ||
        nodeByIndex.get(link.postIndex)?.id === hovered;
      if (!touchesHover) return 'rgba(0,0,0,0)';
      return withAlpha(polarityColor(link.sign), 0.85);
    }

    // The propagation cue: a connection is lit on the step its presynaptic
    // neuron fired. That is what "the signal travelled along this synapse"
    // looks like in this model, where transmission takes exactly one step.
    const current = frameRef.current;
    if (current && current.spiked[link.preIndex] === 1) {
      return withAlpha(polarityColor(link.sign), ACTIVE_EDGE_ALPHA);
    }
    return withAlpha(polarityColor(link.sign), DIM_EDGE_ALPHA);
  }, [nodeByIndex]);

  const linkWidth = useCallback((link: GraphLink) => {
    const current = frameRef.current;
    const lit = current ? current.spiked[link.preIndex] === 1 : false;
    return lit ? link.width * 1.7 : link.width;
  }, []);

  const drawGroupLabels = useCallback(
    (ctx: CanvasRenderingContext2D, globalScale: number) => {
      const groups = groupsRef.current;
      if (groups.length === 0) return;
      const size = Math.max(9, 12 / globalScale);

      ctx.save();
      ctx.font = `${size}px ui-sans-serif, system-ui, sans-serif`;
      ctx.textBaseline = 'middle';

      for (const group of groups) {
        const dim =
          highlightRef.current !== null && highlightRef.current !== group.cellType;
        // Arc under the group, so the grouping is visible even where two
        // neighbouring types have similar node counts.
        ctx.beginPath();
        ctx.arc(0, 0, group.radius + 14, group.startAngle, group.endAngle);
        ctx.lineWidth = Math.max(1, 2 / globalScale);
        ctx.strokeStyle = dim ? 'rgba(104, 117, 141, 0.18)' : 'rgba(122, 140, 172, 0.5)';
        ctx.stroke();

        // One line per group, anchored so the text radiates outwards. Two
        // stacked centred lines collided badly on the near-horizontal arcs.
        const cos = Math.cos(group.midAngle);
        ctx.textAlign = Math.abs(cos) < 0.25 ? 'center' : cos > 0 ? 'left' : 'right';
        ctx.fillStyle = dim ? 'rgba(104, 117, 141, 0.35)' : '#9aa7bf';
        ctx.fillText(
          `${group.label} · ${group.count}`,
          cos * (group.radius + 26),
          Math.sin(group.midAngle) * (group.radius + 26),
        );
      }

      // Hemisphere labels, once per side, at the outer edge of its span.
      const bySide = new Map<string, GroupArc[]>();
      for (const group of groups) {
        const list = bySide.get(group.side) ?? [];
        list.push(group);
        bySide.set(group.side, list);
      }
      ctx.font = `${Math.max(11, 15 / globalScale)}px ui-sans-serif, system-ui, sans-serif`;
      ctx.fillStyle = 'rgba(104, 117, 141, 0.85)';
      for (const [side, list] of bySide) {
        const start = Math.min(...list.map((g) => g.startAngle));
        const end = Math.max(...list.map((g) => g.endAngle));
        const mid = (start + end) / 2;
        const cos = Math.cos(mid);
        // Anchored outwards, like the group labels: a centred label at the
        // horizontal extremes runs straight back over the ring.
        ctx.textAlign = Math.abs(cos) < 0.25 ? 'center' : cos > 0 ? 'left' : 'right';
        ctx.fillText(
          `hemisfério ${side}`,
          cos * (groups[0].radius + 74),
          Math.sin(mid) * (groups[0].radius + 74),
        );
      }
      ctx.restore();
    },
    [],
  );

  const handleNodeHover = useCallback(
    (node: GraphNode | null) => {
      hoverRef.current = node ? node.id : null;
      neighboursRef.current = node
        ? adjacency.get(node.index) ?? new Set<number>()
        : new Set<number>();
    },
    [adjacency],
  );

  const handleNodeClick = useCallback(
    (node: GraphNode) => {
      onSelectNeuron(selectedRef.current === node.id ? null : node.id);
    },
    [onSelectNeuron],
  );

  return (
    <ForceGraph2D<GraphNode, GraphLink>
      ref={fgRef}
      graphData={graphData}
      width={width}
      height={height}
      backgroundColor="#070a10"
      /* Repaint every animation frame: the activation vector changes outside
         React's render cycle, so the engine must not pause on "nothing moved". */
      autoPauseRedraw={false}
      cooldownTicks={layout === 'force' ? 220 : 0}
      d3VelocityDecay={0.32}
      enableNodeDrag={false}
      nodeRelSize={1}
      nodeCanvasObject={paintNode}
      nodePointerAreaPaint={paintPointerArea}
      nodeLabel={(node: GraphNode) => nodeTooltip(node)}
      linkVisibility={showEdges}
      linkColor={linkColor}
      linkWidth={linkWidth}
      linkDirectionalArrowLength={0}
      linkCurvature={layout === 'ring' ? 0.14 : 0}
      onRenderFramePost={drawGroupLabels}
      onNodeHover={handleNodeHover}
      onNodeClick={handleNodeClick}
      onBackgroundClick={() => onSelectNeuron(null)}
    />
  );
}

function withAlpha(hex: string, alpha: number): string {
  const value = hex.replace('#', '');
  const r = parseInt(value.slice(0, 2), 16);
  const g = parseInt(value.slice(2, 4), 16);
  const b = parseInt(value.slice(4, 6), 16);
  return `rgba(${r}, ${g}, ${b}, ${alpha})`;
}

/** Hover card. Every field is either the backend's value or "não disponível". */
function nodeTooltip(node: GraphNode): string {
  const n = node.neuron;
  const na = '<span style="color:#68758d">não disponível</span>';
  const row = (label: string, value: string) =>
    `<div style="display:flex;gap:10px;justify-content:space-between"><span style="color:#9aa7bf">${label}</span><span>${value}</span></div>`;
  return [
    '<div style="font:12.5px ui-sans-serif,system-ui,sans-serif;background:#121826;border:1px solid #35415a;border-radius:8px;padding:9px 11px;color:#e8edf6;min-width:230px">',
    `<div style="font-family:ui-monospace,monospace;font-size:11px;color:#9aa7bf;margin-bottom:6px">${n.root_id}</div>`,
    row('tipo celular', n.cell_type ?? na),
    row('hemisfério', n.side ?? na),
    row('polaridade', n.polarity ?? na),
    row(
      'neurotransmissor',
      n.neurotransmitter
        ? `${n.neurotransmitter}<span style="color:#68758d"> (${n.neurotransmitter_source ?? '?'})</span>`
        : na,
    ),
    row('conexões', `${n.in_degree} entrada / ${n.out_degree} saída`),
    row('sinapses', `${n.in_synapses} entrada / ${n.out_synapses} saída`),
    '</div>',
  ].join('');
}
