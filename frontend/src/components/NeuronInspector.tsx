import type { MaterialisedFrame } from '../api/protocol';
import type { Neuron } from '../api/types';
import { activationColor, POLARITY_LABELS, polarityOfSign } from '../graph/encoding';

export interface NeuronInspectorProps {
  neuron: Neuron | null;
  frame: MaterialisedFrame | null;
  step: number;
  isStimulated: boolean;
  isSource: boolean;
  onUseAsSource: (rootId: string) => void;
}

/** "não disponível" — never a plausible-looking placeholder. */
const NA = <span className="na">não disponível</span>;

export function NeuronInspector({
  neuron,
  frame,
  step,
  isStimulated,
  isSource,
  onUseAsSource,
}: NeuronInspectorProps) {
  if (!neuron) {
    return (
      <section className="panel" aria-labelledby="inspector-heading">
        <h2 id="inspector-heading" className="panel__heading">
          Inspetor
        </h2>
        <p className="hint hint--empty">
          Clique em um neurônio no grafo para ver os dados que o FlyWire traz
          sobre ele.
        </p>
      </section>
    );
  }

  const activation = frame ? frame.activation[neuron.index] ?? 0 : null;
  const spiked = frame ? frame.spiked[neuron.index] === 1 : false;
  const polarity = polarityOfSign(neuron.sign);

  return (
    <section className="panel" aria-labelledby="inspector-heading">
      <h2 id="inspector-heading" className="panel__heading">
        Inspetor
      </h2>

      <p className="inspector__id mono" title="FlyWire root_id">
        {neuron.root_id}
      </p>

      <dl className="kv">
        <dt>tipo celular</dt>
        <dd>{neuron.cell_type ?? NA}</dd>
        <dt>hemisfério</dt>
        <dd>{neuron.side ?? NA}</dd>
        <dt>polaridade</dt>
        <dd>
          {neuron.polarity ?? POLARITY_LABELS[polarity]}{' '}
          <span className="mono muted">(sign {neuron.sign})</span>
        </dd>
        <dt>neurotransmissor</dt>
        <dd>
          {neuron.neurotransmitter ?? NA}
          {neuron.neurotransmitter_source && (
            <span className="tag tag--sm mono">{neuron.neurotransmitter_source}</span>
          )}
        </dd>
        <dt>conexões</dt>
        <dd className="mono">
          {neuron.in_degree} entrada / {neuron.out_degree} saída
        </dd>
        <dt>sinapses</dt>
        <dd className="mono">
          {neuron.in_synapses} entrada / {neuron.out_synapses} saída
        </dd>
        <dt>soma (voxel)</dt>
        <dd className="mono">
          {neuron.position.x !== null &&
          neuron.position.y !== null &&
          neuron.position.z !== null
            ? `${neuron.position.x}, ${neuron.position.y}, ${neuron.position.z}`
            : NA}
        </dd>
      </dl>

      <div className="inspector__state">
        <div className="inspector__state-row">
          <span
            className="swatch"
            style={{ background: activationColor(activation ?? 0) }}
            aria-hidden="true"
          />
          <span>
            {activation === null ? (
              <>ativação {NA} — nenhuma simulação carregada</>
            ) : (
              <>
                ativação no passo <span className="mono">{step}</span>:{' '}
                <span className="mono">{activation.toFixed(3)}</span>
              </>
            )}
          </span>
        </div>
        {spiked && <p className="tag tag--spike">disparou neste passo</p>}
        {isStimulated && <p className="tag tag--stim">origem do estímulo desta execução</p>}
      </div>

      <button
        type="button"
        className="btn btn--ghost btn--block btn--sm"
        onClick={() => onUseAsSource(neuron.root_id)}
        disabled={isSource}
      >
        {isSource
          ? 'já está na lista de origem'
          : 'usar como origem do estímulo'}
      </button>
    </section>
  );
}
