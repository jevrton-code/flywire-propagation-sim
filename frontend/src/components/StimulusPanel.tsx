import type { CellTypeOption, ModelDefaultsResponse, StimulusPreset } from '../api/types';
import {
  buildSource,
  countSelected,
  MODEL_PARAM_FIELDS,
  type SourceMode,
  type StimulusForm,
} from '../state/stimulus';

export interface StimulusPanelProps {
  form: StimulusForm;
  onChange: (next: StimulusForm) => void;
  presets: StimulusPreset[];
  cellTypes: CellTypeOption[];
  sides: string[];
  defaults: ModelDefaultsResponse | null;
  /** Root id currently selected in the graph, offered as a one-click source. */
  selectedRootId: string | null;
  isRunning: boolean;
  onRun: () => void;
  onCancel: () => void;
}

const MODE_LABELS: Record<SourceMode, string> = {
  preset: 'Estímulos prontos',
  'cell-type': 'Por tipo celular',
  neurons: 'Neurônios escolhidos',
};

const PARAM_LABELS: Record<string, string> = {
  threshold: 'limiar (threshold)',
  leak: 'vazamento (leak)',
  gain: 'ganho (gain)',
  refractory_steps: 'passos refratários',
  noise_std: 'ruído (desvio padrão)',
  seed: 'semente (seed)',
};

export function StimulusPanel(props: StimulusPanelProps) {
  const {
    form,
    onChange,
    presets,
    cellTypes,
    sides,
    defaults,
    selectedRootId,
    isRunning,
    onRun,
    onCancel,
  } = props;

  const validation = buildSource(form, presets);
  const patch = (next: Partial<StimulusForm>) => onChange({ ...form, ...next });

  const selectedCount =
    form.mode === 'cell-type'
      ? countSelected(form.cellTypes, form.side, cellTypes)
      : form.mode === 'neurons'
        ? form.rootIds.length
        : null;

  const maxSteps = defaults?.limits.max_steps ?? 500;
  const maxAmplitude = defaults?.limits.max_amplitude ?? 100;

  return (
    <section className="panel" aria-labelledby="stimulus-heading">
      <h2 id="stimulus-heading" className="panel__heading">
        1 · Origem do estímulo
      </h2>

      <div className="segmented" role="tablist" aria-label="Modo de seleção da origem">
        {(Object.keys(MODE_LABELS) as SourceMode[]).map((mode) => (
          <button
            key={mode}
            type="button"
            role="tab"
            aria-selected={form.mode === mode}
            className={`segmented__item ${form.mode === mode ? 'is-active' : ''}`}
            onClick={() => patch({ mode })}
          >
            {MODE_LABELS[mode]}
          </button>
        ))}
      </div>

      {form.mode === 'preset' && (
        <div className="preset-list">
          {presets.length === 0 && (
            <p className="hint">Nenhum estímulo pronto foi devolvido pela API.</p>
          )}
          {presets.map((preset) => (
            <label
              key={preset.id}
              className={`preset ${form.presetId === preset.id ? 'is-active' : ''}`}
            >
              <input
                type="radio"
                name="preset"
                value={preset.id}
                checked={form.presetId === preset.id}
                onChange={() => patch({ presetId: preset.id })}
              />
              <span>
                <span className="preset__label">{preset.label}</span>
                <span className="preset__description">{preset.description}</span>
              </span>
            </label>
          ))}
        </div>
      )}

      {form.mode === 'cell-type' && (
        <div className="field-group">
          <fieldset className="fieldset">
            <legend className="label">Tipos celulares</legend>
            <div className="checkbox-grid">
              {cellTypes.map((option) => (
                <label key={option.cell_type} className="checkbox">
                  <input
                    type="checkbox"
                    checked={form.cellTypes.includes(option.cell_type)}
                    onChange={(event) =>
                      patch({
                        cellTypes: event.target.checked
                          ? [...form.cellTypes, option.cell_type]
                          : form.cellTypes.filter((t) => t !== option.cell_type),
                      })
                    }
                  />
                  <span className="checkbox__label">
                    {option.cell_type}
                    <span className="checkbox__meta">
                      {option.count} · {option.polarity}
                    </span>
                  </span>
                </label>
              ))}
            </div>
          </fieldset>

          <label className="field">
            <span className="label">Hemisfério</span>
            <select
              className="input"
              value={form.side ?? ''}
              onChange={(event) =>
                patch({ side: (event.target.value || null) as 'left' | 'right' | null })
              }
            >
              <option value="">ambos</option>
              {sides.map((side) => (
                <option key={side} value={side}>
                  {side}
                </option>
              ))}
            </select>
          </label>
        </div>
      )}

      {form.mode === 'neurons' && (
        <div className="field-group">
          <p className="hint">
            Clique em um neurônio no grafo e use o botão do inspetor para adicioná-lo
            aqui. Os identificadores são root_ids reais do FlyWire.
          </p>
          {selectedRootId && !form.rootIds.includes(selectedRootId) && (
            <button
              type="button"
              className="btn btn--ghost btn--sm"
              onClick={() => patch({ rootIds: [...form.rootIds, selectedRootId] })}
            >
              + adicionar o neurônio selecionado
            </button>
          )}
          <ul className="chip-list">
            {form.rootIds.length === 0 && (
              <li className="hint hint--empty">nenhum neurônio escolhido</li>
            )}
            {form.rootIds.map((rootId) => (
              <li key={rootId} className="chip">
                <span className="mono">{rootId}</span>
                <button
                  type="button"
                  aria-label={`Remover o neurônio ${rootId}`}
                  onClick={() =>
                    patch({ rootIds: form.rootIds.filter((r) => r !== rootId) })
                  }
                >
                  ×
                </button>
              </li>
            ))}
          </ul>
        </div>
      )}

      {selectedCount !== null && (
        <p className="hint" data-testid="selection-count">
          {selectedCount} neurônio{selectedCount === 1 ? '' : 's'} receberá
          {selectedCount === 1 ? '' : 'ão'} o estímulo.
        </p>
      )}

      <h2 className="panel__heading panel__heading--spaced">2 · Estímulo e duração</h2>

      <div className="field-group">
        <label className="field">
          <span className="label">
            Passos simulados <span className="value mono">{form.steps}</span>
          </span>
          <input
            type="range"
            min={2}
            max={Math.min(200, maxSteps)}
            step={1}
            value={form.steps}
            onChange={(event) => {
              const steps = Number(event.target.value);
              patch({ steps, duration: Math.min(form.duration, steps) });
            }}
          />
        </label>

        <label className="field">
          <span className="label">
            Amplitude da corrente <span className="value mono">{form.amplitude}</span>
          </span>
          <input
            type="range"
            min={0.1}
            max={Math.min(10, maxAmplitude)}
            step={0.1}
            value={form.amplitude}
            onChange={(event) => patch({ amplitude: Number(event.target.value) })}
          />
        </label>

        <label className="field">
          <span className="label">
            Duração do estímulo <span className="value mono">{form.duration} passos</span>
          </span>
          <input
            type="range"
            min={1}
            max={Math.min(40, form.steps)}
            step={1}
            value={Math.min(form.duration, form.steps)}
            onChange={(event) => patch({ duration: Number(event.target.value) })}
          />
        </label>
      </div>

      <details className="disclosure">
        <summary>Parâmetros do modelo LIF</summary>
        <p className="hint">
          Deixe em branco para usar o padrão do servidor (mostrado como
          espaço reservado). Nenhum valor é preenchido por este cliente.
        </p>
        <div className="param-grid">
          {MODEL_PARAM_FIELDS.map((key) => {
            const fallback = defaults?.parameters?.[key];
            return (
              <label key={key} className="field field--inline">
                <span className="label">{PARAM_LABELS[key] ?? key}</span>
                <input
                  className="input input--sm mono"
                  type="number"
                  step="any"
                  placeholder={
                    fallback === undefined || fallback === null
                      ? 'não disponível'
                      : String(fallback)
                  }
                  value={form.params[key] ?? ''}
                  onChange={(event) =>
                    patch({ params: { ...form.params, [key]: event.target.value } })
                  }
                />
              </label>
            );
          })}
        </div>
      </details>

      <div className="run-row">
        {isRunning ? (
          <button type="button" className="btn btn--danger btn--block" onClick={onCancel}>
            Interromper simulação
          </button>
        ) : (
          <button
            type="button"
            className="btn btn--primary btn--block"
            onClick={onRun}
            disabled={!validation.ok}
          >
            Injetar estímulo e simular
          </button>
        )}
        {!validation.ok && <p className="hint hint--warn">{validation.reason}</p>}
      </div>
    </section>
  );
}
