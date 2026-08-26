import { activationColor, POLARITY_COLORS } from '../graph/encoding';
import type { CellTypeOption, CircuitSummary } from '../api/types';

export interface LegendProps {
  summary: CircuitSummary;
  cellTypes: CellTypeOption[];
  highlightedCellType: string | null;
  onHighlight: (cellType: string | null) => void;
}

/**
 * Explains every visual channel on the canvas.
 *
 * The swatches are generated from the same `encoding` module the canvas draws
 * with, so the legend cannot drift out of sync with what is on screen.
 */
export function Legend({
  summary,
  cellTypes,
  highlightedCellType,
  onHighlight,
}: LegendProps) {
  const rampStops = [0, 0.25, 0.5, 0.75, 1];
  const gradient = `linear-gradient(90deg, ${rampStops
    .map((t) => `${activationColor(t)} ${t * 100}%`)
    .join(', ')})`;

  return (
    <section className="panel legend" aria-labelledby="legend-heading">
      <h2 id="legend-heading" className="panel__heading">
        Legenda
      </h2>

      <div className="legend__block">
        <p className="legend__title">Cor do nó — ativação no passo atual</p>
        <div className="legend__ramp" style={{ background: gradient }} aria-hidden="true" />
        <div className="legend__ramp-labels mono">
          <span>0 · em repouso</span>
          <span>1 · ativação máxima</span>
        </div>
        <p className="legend__note">
          Traço exponencial suavizado sobre os disparos, usado só para
          visualização — não é taxa de disparo em Hz.
        </p>
      </div>

      <div className="legend__block">
        <p className="legend__title">Forma do nó — polaridade</p>
        <ul className="legend__rows">
          <li>
            <ShapeSwatch shape="circle" color={POLARITY_COLORS.excitatory} />
            <span>excitatório</span>
            <span className="legend__count mono">
              {summary.n_excitatory_neurons ?? 'não disponível'}
            </span>
          </li>
          <li>
            <ShapeSwatch shape="square" color={POLARITY_COLORS.inhibitory} />
            <span>inibitório</span>
            <span className="legend__count mono">
              {summary.n_inhibitory_neurons ?? 'não disponível'}
            </span>
          </li>
          <li>
            <ShapeSwatch shape="triangle" color={POLARITY_COLORS.modulatory} />
            <span>modulatório</span>
            <span className="legend__count mono">
              {summary.n_modulatory_neurons ?? 'não disponível'}
            </span>
          </li>
        </ul>
        <p className="legend__note">
          A polaridade é codificada pela forma (e não só pela cor) para continuar
          legível junto com a escala de ativação.
        </p>
      </div>

      <div className="legend__block">
        <p className="legend__title">Marcações</p>
        <ul className="legend__rows">
          <li>
            <MarkSwatch kind="spike" />
            <span>disparou neste passo</span>
          </li>
          <li>
            <MarkSwatch kind="stimulus" />
            <span>origem do estímulo</span>
          </li>
          <li>
            <MarkSwatch kind="size" />
            <span>tamanho = sinapses totais (entrada + saída)</span>
          </li>
        </ul>
      </div>

      <div className="legend__block">
        <p className="legend__title">Arestas — sinapses reais</p>
        <ul className="legend__rows">
          <li>
            <span
              className="legend__line"
              style={{ background: POLARITY_COLORS.excitatory }}
            />
            <span>conexão excitatória</span>
          </li>
          <li>
            <span
              className="legend__line"
              style={{ background: POLARITY_COLORS.inhibitory }}
            />
            <span>conexão inibitória</span>
          </li>
        </ul>
        <p className="legend__note">
          Uma aresta acende no passo em que o neurônio pré-sináptico dispara. A
          espessura cresce com o número de sinapses da conexão.
        </p>
      </div>

      <div className="legend__block">
        <p className="legend__title">Tipos celulares</p>
        <ul className="legend__types">
          {cellTypes.map((option) => (
            <li key={option.cell_type}>
              <button
                type="button"
                className={`legend__type ${
                  highlightedCellType === option.cell_type ? 'is-active' : ''
                }`}
                onMouseEnter={() => onHighlight(option.cell_type)}
                onMouseLeave={() => onHighlight(null)}
                onFocus={() => onHighlight(option.cell_type)}
                onBlur={() => onHighlight(null)}
                onClick={() =>
                  onHighlight(
                    highlightedCellType === option.cell_type ? null : option.cell_type,
                  )
                }
              >
                <span>{option.cell_type}</span>
                <span className="legend__count mono">{option.count}</span>
              </button>
            </li>
          ))}
        </ul>
        <p className="legend__note">
          Passe o mouse (ou clique) para destacar o tipo no grafo.
        </p>
      </div>
    </section>
  );
}

function ShapeSwatch({
  shape,
  color,
}: {
  shape: 'circle' | 'square' | 'triangle';
  color: string;
}) {
  const fill = activationColor(0.55);
  return (
    <svg width="18" height="18" viewBox="0 0 18 18" aria-hidden="true">
      {shape === 'circle' && (
        <circle cx="9" cy="9" r="6" fill={fill} stroke={color} strokeWidth="1.6" />
      )}
      {shape === 'square' && (
        <rect x="3.5" y="3.5" width="11" height="11" fill={fill} stroke={color} strokeWidth="1.6" />
      )}
      {shape === 'triangle' && (
        <polygon points="9,2.5 16,14.5 2,14.5" fill={fill} stroke={color} strokeWidth="1.6" />
      )}
    </svg>
  );
}

function MarkSwatch({ kind }: { kind: 'spike' | 'stimulus' | 'size' }) {
  if (kind === 'size') {
    return (
      <svg width="34" height="18" viewBox="0 0 34 18" aria-hidden="true">
        <circle cx="6" cy="9" r="3" fill={activationColor(0.35)} stroke="#b4c4e0" strokeWidth="1" />
        <circle cx="18" cy="9" r="5" fill={activationColor(0.35)} stroke="#b4c4e0" strokeWidth="1" />
        <circle cx="29" cy="9" r="7" fill={activationColor(0.35)} stroke="#b4c4e0" strokeWidth="1" />
      </svg>
    );
  }
  if (kind === 'spike') {
    return (
      <svg width="18" height="18" viewBox="0 0 18 18" aria-hidden="true">
        <circle cx="9" cy="9" r="8" fill="rgba(255, 236, 178, 0.22)" />
        <circle cx="9" cy="9" r="5" fill={activationColor(0.95)} stroke="#fff4d6" strokeWidth="1.8" />
      </svg>
    );
  }
  return (
    <svg width="18" height="18" viewBox="0 0 18 18" aria-hidden="true">
      <circle cx="9" cy="9" r="4.5" fill={activationColor(0.2)} stroke="#b4c4e0" strokeWidth="1" />
      <circle
        cx="9"
        cy="9"
        r="7.4"
        fill="none"
        stroke="#7dd8ff"
        strokeWidth="1.3"
        strokeDasharray="2.4 2.2"
      />
    </svg>
  );
}
