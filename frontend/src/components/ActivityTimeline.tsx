import { useEffect, useMemo, useRef, useState } from 'react';
import type { MaterialisedFrame } from '../api/protocol';
import type { Neuron } from '../api/types';
import { activationColor } from '../graph/encoding';

export interface ActivityTimelineProps {
  neurons: Neuron[];
  cellTypeOrder: string[];
  frames: MaterialisedFrame[];
  currentStep: number;
  expectedFrames: number | null;
  onSeek: (step: number) => void;
}

const ROW_HEIGHT = 15;
const ROW_GAP = 2;
const LABEL_WIDTH = 92;

/**
 * Per-cell-type activity over time: rows are cell types, columns are steps,
 * brightness is the mean activation of that type at that step.
 *
 * The graph answers "where"; this answers "when, and in what order". Reading
 * left to right it is immediately visible that, say, EPG lights up before
 * Delta7 — which is the actual claim a propagation demo is making, and it is
 * hard to be sure of from an animation alone.
 *
 * Drawn on a canvas: a 200-step run across 6 rows is 1 200 cells, and as DOM
 * elements that would be re-styled on every playback tick.
 */
export function ActivityTimeline({
  neurons,
  cellTypeOrder,
  frames,
  currentStep,
  expectedFrames,
  onSeek,
}: ActivityTimelineProps) {
  const canvasRef = useRef<HTMLCanvasElement | null>(null);
  const wrapperRef = useRef<HTMLDivElement | null>(null);
  const [width, setWidth] = useState(600);

  const rows = useMemo(() => {
    const present = cellTypeOrder.filter((type) =>
      neurons.some((n) => n.cell_type === type),
    );
    const extra = Array.from(
      new Set(
        neurons
          .map((n) => n.cell_type)
          .filter((t): t is string => t !== null && !present.includes(t)),
      ),
    );
    const withoutType = neurons.filter((n) => n.cell_type === null);
    const labels = [...present, ...extra];
    const indices = labels.map((type) =>
      neurons.filter((n) => n.cell_type === type).map((n) => n.index),
    );
    if (withoutType.length > 0) {
      labels.push('não disponível');
      indices.push(withoutType.map((n) => n.index));
    }
    return labels.map((label, i) => ({ label, indices: indices[i] }));
  }, [neurons, cellTypeOrder]);

  useEffect(() => {
    const element = wrapperRef.current;
    if (!element) return;
    const observer = new ResizeObserver((entries) => {
      const next = entries[0]?.contentRect.width;
      if (next && next > 0) setWidth(next);
    });
    observer.observe(element);
    setWidth(element.clientWidth || 600);
    return () => observer.disconnect();
  }, []);

  const height = rows.length * (ROW_HEIGHT + ROW_GAP) + 16;

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    const dpr = window.devicePixelRatio || 1;
    canvas.width = Math.max(1, Math.round(width * dpr));
    canvas.height = Math.max(1, Math.round(height * dpr));
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    ctx.clearRect(0, 0, width, height);

    const columns = Math.max(1, expectedFrames ?? frames.length);
    const plotWidth = Math.max(1, width - LABEL_WIDTH - 8);
    const columnWidth = plotWidth / columns;

    rows.forEach((row, rowIndex) => {
      const y = rowIndex * (ROW_HEIGHT + ROW_GAP) + 4;

      ctx.fillStyle = '#9aa7bf';
      ctx.font = '11px ui-sans-serif, system-ui, sans-serif';
      ctx.textAlign = 'right';
      ctx.textBaseline = 'middle';
      ctx.fillText(row.label, LABEL_WIDTH - 8, y + ROW_HEIGHT / 2, LABEL_WIDTH - 12);

      // Not-yet-received part of the run, so a partial stream looks partial.
      ctx.fillStyle = '#0e1420';
      ctx.fillRect(LABEL_WIDTH, y, plotWidth, ROW_HEIGHT);

      for (let step = 0; step < frames.length; step += 1) {
        const activation = frames[step].activation;
        let sum = 0;
        for (const index of row.indices) sum += activation[index] ?? 0;
        const mean = row.indices.length ? sum / row.indices.length : 0;
        ctx.fillStyle = activationColor(mean);
        ctx.fillRect(
          LABEL_WIDTH + step * columnWidth,
          y,
          Math.max(1, columnWidth + 0.5),
          ROW_HEIGHT,
        );
      }
    });

    if (frames.length > 0) {
      const x = LABEL_WIDTH + (currentStep + 0.5) * columnWidth;
      ctx.strokeStyle = '#ffffff';
      ctx.lineWidth = 1.4;
      ctx.beginPath();
      ctx.moveTo(x, 2);
      ctx.lineTo(x, height - 10);
      ctx.stroke();
    }
  }, [rows, frames, currentStep, width, height, expectedFrames]);

  const handleClick = (event: React.MouseEvent<HTMLCanvasElement>) => {
    if (frames.length === 0) return;
    const rect = event.currentTarget.getBoundingClientRect();
    const columns = Math.max(1, expectedFrames ?? frames.length);
    const plotWidth = Math.max(1, rect.width - LABEL_WIDTH - 8);
    const x = event.clientX - rect.left - LABEL_WIDTH;
    const step = Math.floor((x / plotWidth) * columns);
    onSeek(Math.max(0, Math.min(frames.length - 1, step)));
  };

  return (
    <div className="timeline" ref={wrapperRef}>
      <div className="timeline__header">
        <span className="timeline__title">Ativação média por tipo celular</span>
        <span className="timeline__axis mono">
          passo 0 → {expectedFrames ? expectedFrames - 1 : Math.max(0, frames.length - 1)}
        </span>
      </div>
      <canvas
        ref={canvasRef}
        style={{ width: '100%', height }}
        onClick={handleClick}
        role="img"
        aria-label={
          frames.length
            ? `Mapa de ativação média por tipo celular ao longo de ${frames.length} passos`
            : 'Mapa de ativação vazio: nenhuma simulação executada'
        }
      />
      {frames.length === 0 && (
        <p className="hint hint--empty">
          rode uma simulação para ver a ordem em que cada tipo celular é recrutado
        </p>
      )}
    </div>
  );
}
