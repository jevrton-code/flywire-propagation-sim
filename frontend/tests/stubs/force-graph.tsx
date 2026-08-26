/**
 * Test double for `react-force-graph-2d`.
 *
 * The real component draws into a canvas 2D context, which jsdom does not
 * implement. This stub keeps the same props contract and renders the data it
 * was given as DOM, so a test can assert *what the app asked to be drawn*
 * (which nodes, which links, which are stimulated) and can trigger
 * `onNodeClick` without simulating canvas hit-testing.
 */
import type { ReactElement } from 'react';

interface StubNode {
  id: string;
  index: number;
  neuron?: { cell_type: string | null; root_id: string };
}

interface StubProps {
  graphData: { nodes: StubNode[]; links: unknown[] };
  width?: number;
  height?: number;
  onNodeClick?: (node: StubNode, event: MouseEvent) => void;
  onBackgroundClick?: (event: MouseEvent) => void;
  [key: string]: unknown;
}

export default function ForceGraph2DStub(props: StubProps): ReactElement {
  const { graphData, width, height, onNodeClick, onBackgroundClick } = props;
  return (
    <div
      data-testid="force-graph"
      data-node-count={graphData.nodes.length}
      data-link-count={graphData.links.length}
      data-width={width}
      data-height={height}
    >
      <button
        type="button"
        data-testid="graph-background"
        onClick={() => onBackgroundClick?.(new MouseEvent('click'))}
      >
        fundo
      </button>
      {graphData.nodes.map((node) => (
        <button
          key={node.id}
          type="button"
          data-testid="graph-node"
          data-root-id={node.id}
          data-cell-type={node.neuron?.cell_type ?? ''}
          onClick={() => onNodeClick?.(node, new MouseEvent('click'))}
        >
          {node.id}
        </button>
      ))}
    </div>
  );
}

export type ForceGraphMethods<N = unknown, L = unknown> = {
  zoomToFit: (ms?: number, padding?: number) => void;
  d3ReheatSimulation: () => void;
  _node?: N;
  _link?: L;
};
