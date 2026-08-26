import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import {
  ApiError,
  fetchCellTypes,
  fetchGraph,
  fetchModelDefaults,
  fetchProvenance,
} from './api/client';
import type {
  CellTypeListResponse,
  GraphResponse,
  ModelDefaultsResponse,
  ProvenanceResponse,
} from './api/types';
import { useSimulationSocket } from './api/useSimulationSocket';
import { ActivityTimeline } from './components/ActivityTimeline';
import { Legend } from './components/Legend';
import { ModelNotice, ProvenanceBar } from './components/ModelNotice';
import { NeuronInspector } from './components/NeuronInspector';
import { PlaybackControls } from './components/PlaybackControls';
import { RunReport } from './components/RunReport';
import { errorBannerCopy, StatusBanner } from './components/StatusBanner';
import { StimulusPanel } from './components/StimulusPanel';
import { GraphView } from './graph/GraphView';
import { LAYOUT_DESCRIPTIONS, LAYOUT_LABELS, type LayoutId } from './graph/layouts';
import { useElementSize } from './hooks/useElementSize';
import { buildRequest, buildSource, DEFAULT_FORM, type StimulusForm } from './state/stimulus';
import { usePlayback } from './state/usePlayback';

interface CircuitData {
  graph: GraphResponse;
  cellTypes: CellTypeListResponse;
  provenance: ProvenanceResponse | null;
  defaults: ModelDefaultsResponse | null;
}

export default function App() {
  const [data, setData] = useState<CircuitData | null>(null);
  const [loadError, setLoadError] = useState<{ message: string; code: string } | null>(null);
  const [loading, setLoading] = useState(true);
  const [reloadToken, setReloadToken] = useState(0);

  const [form, setForm] = useState<StimulusForm>(DEFAULT_FORM);
  const [layout, setLayout] = useState<LayoutId>('ring');
  // Display-only filter. It never touches the simulation, which always runs on
  // every connection; the default hides the long tail of weak connections that
  // otherwise saturates the view into a solid disc.
  const [minSynapses, setMinSynapses] = useState(15);
  const [showEdges, setShowEdges] = useState(true);
  const [selectedRootId, setSelectedRootId] = useState<string | null>(null);
  const [highlightedCellType, setHighlightedCellType] = useState<string | null>(null);

  const socket = useSimulationSocket();
  const { state } = socket;

  // ---- data loading -------------------------------------------------------
  useEffect(() => {
    const controller = new AbortController();
    setLoading(true);
    setLoadError(null);

    // The graph is the only required call; provenance and defaults enrich the
    // page but must not block it, so their failures degrade instead of erroring.
    Promise.all([
      fetchGraph(undefined, controller.signal),
      fetchCellTypes(undefined, controller.signal),
      fetchProvenance(undefined, controller.signal).catch(() => null),
      fetchModelDefaults(controller.signal).catch(() => null),
    ])
      .then(([graph, cellTypes, provenance, defaults]) => {
        if (controller.signal.aborted) return;
        setData({ graph, cellTypes, provenance, defaults });
        setForm((current) => ({
          ...current,
          presetId: current.presetId ?? cellTypes.presets[0]?.id ?? null,
        }));
        setLoading(false);
      })
      .catch((cause) => {
        if (controller.signal.aborted) return;
        setLoadError({
          code: cause instanceof ApiError ? cause.code : 'unexpected_error',
          message: cause instanceof Error ? cause.message : String(cause),
        });
        setLoading(false);
      });

    return () => controller.abort();
  }, [reloadToken]);

  // ---- run lifecycle ------------------------------------------------------
  const runKeyRef = useRef(0);
  const [runKey, setRunKey] = useState(0);
  useEffect(() => {
    if (state.header) {
      runKeyRef.current += 1;
      setRunKey(runKeyRef.current);
    }
  }, [state.header]);

  const isStreaming = state.run === 'streaming';
  const playback = usePlayback({
    frameCount: state.frames.length,
    isStreaming,
    runKey,
  });

  const frame = state.frames[playback.step] ?? null;

  const stimulatedIndices = useMemo(
    () => new Set(state.header?.stimulated_indices ?? []),
    [state.header],
  );

  const presets = data?.cellTypes.presets ?? [];
  const validation = useMemo(() => buildSource(form, presets), [form, presets]);

  const run = useCallback(() => {
    if (!validation.ok) return;
    socket.start(buildRequest(form, validation.source, 'known-first'));
  }, [form, socket, validation]);

  // ---- graph sizing -------------------------------------------------------
  const { ref: canvasWrapRef, width, height } = useElementSize<HTMLDivElement>();

  // ---- keyboard -----------------------------------------------------------
  useEffect(() => {
    const onKey = (event: KeyboardEvent) => {
      if (event.code !== 'Space') return;
      const target = event.target as HTMLElement | null;
      if (
        target &&
        ['INPUT', 'SELECT', 'TEXTAREA', 'BUTTON'].includes(target.tagName)
      ) {
        return;
      }
      event.preventDefault();
      playback.toggle();
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [playback]);

  const neuronByRootId = useMemo(() => {
    const map = new Map<string, (typeof data extends null ? never : GraphResponse)['neurons'][number]>();
    for (const neuron of data?.graph.neurons ?? []) map.set(neuron.root_id, neuron);
    return map;
  }, [data]);

  // ---- loading / fatal error ---------------------------------------------
  if (loading) {
    return (
      <div className="boot" role="status" aria-live="polite">
        <div className="boot__spinner" aria-hidden="true" />
        <p className="boot__title">Carregando o subgrafo do conectoma…</p>
        <p className="boot__hint">
          Nós, arestas e proveniência vêm da API em uma única requisição. Se
          demorar, confira se o backend está rodando em{' '}
          <code className="mono">127.0.0.1:8000</code>.
        </p>
      </div>
    );
  }

  if (loadError || !data) {
    return (
      <div className="boot boot--error">
        <StatusBanner
          tone="error"
          title="Não foi possível carregar o circuito"
          message={loadError?.message ?? 'a API não devolveu os dados do grafo.'}
          actionLabel="Tentar de novo"
          onAction={() => setReloadToken((t) => t + 1)}
        />
        <p className="boot__hint">
          Inicie o backend com{' '}
          <code className="mono">python -m flywire_api.run</code> na raiz do
          repositório e recarregue.
        </p>
      </div>
    );
  }

  const { graph, cellTypes, provenance, defaults } = data;
  const summary = graph.summary;
  const selectedNeuron = selectedRootId ? neuronByRootId.get(selectedRootId) ?? null : null;
  const visibleEdges = graph.edges.filter((edge) => edge.syn_count >= minSynapses).length;

  return (
    <div className="app">
      <header className="topbar">
        <div className="topbar__title">
          <h1>Propagação de ativação no conectoma da <em>Drosophila</em></h1>
          <p className="topbar__subtitle">
            {summary.title ?? 'não disponível'} · circuito{' '}
            <code className="mono">{summary.circuit}</code>
          </p>
        </div>
        <a
          className="btn btn--ghost btn--sm"
          href="#modelo-e-dados"
          onClick={(event) => {
            event.preventDefault();
            document.getElementById('modelo-e-dados')?.scrollIntoView({ behavior: 'smooth' });
          }}
        >
          Sobre os dados e o modelo
        </a>
      </header>

      <ProvenanceBar
        summary={summary}
        provenance={provenance}
        onOpenDetails={() =>
          document.getElementById('modelo-e-dados')?.scrollIntoView({ behavior: 'smooth' })
        }
      />

      {state.error && (
        <StatusBanner
          tone="error"
          {...errorBannerCopy(state.error)}
          details={state.error.details ?? null}
          actionLabel="Tentar de novo"
          onAction={run}
        />
      )}
      {state.notice && (
        <StatusBanner
          tone="warning"
          title="Mensagem inesperada do servidor"
          message={state.notice}
          onDismiss={socket.reset}
        />
      )}

      <main className="workspace">
        <aside className="workspace__left">
          <StimulusPanel
            form={form}
            onChange={setForm}
            presets={presets}
            cellTypes={cellTypes.cell_types}
            sides={cellTypes.sides}
            defaults={defaults}
            selectedRootId={selectedRootId}
            isRunning={isStreaming || state.run === 'starting'}
            onRun={run}
            onCancel={socket.cancel}
          />
          <Legend
            summary={summary}
            cellTypes={cellTypes.cell_types}
            highlightedCellType={highlightedCellType}
            onHighlight={setHighlightedCellType}
          />
        </aside>

        <section className="workspace__centre">
          <div className="viewport-toolbar">
            <div className="segmented segmented--sm" role="tablist" aria-label="Layout do grafo">
              {(Object.keys(LAYOUT_LABELS) as LayoutId[]).map((id) => (
                <button
                  key={id}
                  type="button"
                  role="tab"
                  aria-selected={layout === id}
                  className={`segmented__item ${layout === id ? 'is-active' : ''}`}
                  onClick={() => setLayout(id)}
                >
                  {LAYOUT_LABELS[id]}
                </button>
              ))}
            </div>

            <div className="viewport-toolbar__filters">
              <label className="field field--inline">
                <span className="label label--tight">
                  arestas ≥ <span className="mono">{minSynapses}</span> sinapses
                </span>
                <input
                  type="range"
                  min={summary.synapse_threshold ?? 1}
                  max={80}
                  step={1}
                  value={minSynapses}
                  onChange={(event) => setMinSynapses(Number(event.target.value))}
                  disabled={!showEdges}
                />
              </label>
              <span className="mono muted viewport-toolbar__count">
                {visibleEdges.toLocaleString('pt-BR')} /{' '}
                {summary.n_connections.toLocaleString('pt-BR')}
              </span>
              <label className="checkbox checkbox--inline">
                <input
                  type="checkbox"
                  checked={showEdges}
                  onChange={(event) => setShowEdges(event.target.checked)}
                />
                <span className="checkbox__label">mostrar arestas</span>
              </label>
            </div>
          </div>

          <p className="viewport-note">
            {LAYOUT_DESCRIPTIONS[layout]} O filtro de arestas é apenas visual: a
            simulação sempre usa todas as{' '}
            {summary.n_connections.toLocaleString('pt-BR')} conexões.
          </p>

          <div className="viewport" ref={canvasWrapRef}>
            {width > 0 && height > 0 && (
              <GraphView
                neurons={graph.neurons}
                edges={graph.edges}
                cellTypeOrder={summary.cell_types}
                layout={layout}
                width={width}
                height={height}
                frame={frame}
                stimulatedIndices={stimulatedIndices}
                selectedRootId={selectedRootId}
                highlightedCellType={highlightedCellType}
                minSynapses={minSynapses}
                showEdges={showEdges}
                onSelectNeuron={setSelectedRootId}
              />
            )}
            {state.run === 'idle' && (
              <div className="viewport__overlay">
                <p>
                  Escolha uma origem à esquerda e clique em{' '}
                  <strong>“Injetar estímulo e simular”</strong>.
                </p>
              </div>
            )}
            {state.connection === 'connecting' && (
              <div className="viewport__pill">conectando ao servidor…</div>
            )}
          </div>

          <PlaybackControls
            playback={playback}
            frames={state.frames}
            expectedFrames={state.header?.n_frames ?? null}
            isStreaming={isStreaming}
            hasRun={state.header !== null}
            onRerun={run}
            canRerun={validation.ok && !isStreaming}
          />

          <ActivityTimeline
            neurons={graph.neurons}
            cellTypeOrder={summary.cell_types}
            frames={state.frames}
            currentStep={playback.step}
            expectedFrames={state.header?.n_frames ?? null}
            onSeek={playback.seek}
          />
        </section>

        <aside className="workspace__right">
          <NeuronInspector
            neuron={selectedNeuron}
            frame={frame}
            step={playback.step}
            isStimulated={
              selectedNeuron ? stimulatedIndices.has(selectedNeuron.index) : false
            }
            isSource={
              selectedNeuron ? form.rootIds.includes(selectedNeuron.root_id) : false
            }
            onUseAsSource={(rootId) =>
              setForm((current) => ({
                ...current,
                mode: 'neurons',
                rootIds: current.rootIds.includes(rootId)
                  ? current.rootIds
                  : [...current.rootIds, rootId],
              }))
            }
          />
          <RunReport
            report={state.report}
            status={state.run}
            cancelledAtStep={state.cancelledAtStep}
          />
        </aside>
      </main>

      <ModelNotice summary={summary} provenance={provenance} id="modelo-e-dados" />

      <footer className="footer">
        <p>
          Projeto de portfólio de engenharia. A conectividade é medida e pública;
          a dinâmica é um modelo de brinquedo descrito acima.
        </p>
      </footer>
    </div>
  );
}
