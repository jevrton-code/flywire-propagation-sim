import type { CircuitSummary, ProvenanceResponse } from '../api/types';

/**
 * The scientific-honesty surface of the app.
 *
 * Requirement from the project brief: the disclaimer and the model's
 * simplifications must be *visible*, not buried in a tooltip. So there are two
 * pieces here — a bar that is always on screen next to the graph, and a full
 * section listing every simplification the backend reports.
 *
 * All of this text is rendered **verbatim from the API**. It is not translated
 * and not summarised: these are claims about a scientific dataset, and
 * paraphrasing them in the frontend is exactly how a claim quietly stops being
 * true. Only the framing around the quotes is this app's own copy.
 */

const FLYWIRE_URL = 'https://codex.flywire.ai';

export interface ProvenanceBarProps {
  summary: CircuitSummary;
  provenance: ProvenanceResponse | null;
  onOpenDetails: () => void;
}

export function ProvenanceBar({ summary, provenance, onOpenDetails }: ProvenanceBarProps) {
  const version = provenance?.provenance?.dataset?.connectivity?.version ?? null;

  return (
    <div className="provenance-bar">
      <p className="provenance-bar__lead">
        <strong>Conectoma real, dinâmica de brinquedo.</strong>{' '}
        {summary.n_neurons} neurônios e {summary.n_connections.toLocaleString('pt-BR')}{' '}
        conexões ({summary.n_synapses.toLocaleString('pt-BR')} sinapses) medidos no
        cérebro de uma <em>Drosophila melanogaster</em> pelo projeto FlyWire
        {version ? ` (snapshot de conectividade v${version})` : ''}. O modelo de
        propagação é simplificado e não prediz o que neurônios reais fazem.
      </p>
      <div className="provenance-bar__actions">
        <a
          className="link"
          href={FLYWIRE_URL}
          target="_blank"
          rel="noreferrer noopener"
        >
          fonte: codex.flywire.ai ↗
        </a>
        <button type="button" className="btn btn--ghost btn--sm" onClick={onOpenDetails}>
          ver as {summary.simplifications.length} simplificações
        </button>
      </div>
    </div>
  );
}

export interface ModelNoticeProps {
  summary: CircuitSummary;
  provenance: ProvenanceResponse | null;
  id?: string;
}

export function ModelNotice({ summary, provenance, id }: ModelNoticeProps) {
  const dataset = provenance?.provenance?.dataset ?? null;
  const connectivity = dataset?.connectivity ?? null;
  const annotations = dataset?.annotations ?? null;

  return (
    <section className="notice" id={id} aria-labelledby="notice-heading">
      <header className="notice__header">
        <h2 id="notice-heading">O que este simulador é — e o que não é</h2>
        <p className="notice__lead">
          Todo o texto abaixo vem literalmente da API (
          <code className="mono">/api/circuit</code> e{' '}
          <code className="mono">/api/circuit/provenance</code>), em inglês, sem
          tradução nem resumo, para não haver risco de a interface afirmar algo
          diferente do que o backend afirma.
        </p>
      </header>

      <div className="notice__grid">
        <article className="notice__card notice__card--warn">
          <h3>Aviso do modelo</h3>
          <blockquote className="quote">{summary.disclaimer}</blockquote>
          <h3 className="notice__subheading">
            Simplificações assumidas ({summary.simplifications.length})
          </h3>
          <ul className="notice__list">
            {summary.simplifications.map((item) => (
              <li key={item}>{item}</li>
            ))}
          </ul>
        </article>

        <article className="notice__card">
          <h3>De onde vêm os dados</h3>
          <dl className="kv">
            <dt>circuito</dt>
            <dd>{summary.title ?? 'não disponível'}</dd>
            <dt>neurônios</dt>
            <dd className="mono">{summary.n_neurons}</dd>
            <dt>conexões</dt>
            <dd className="mono">{summary.n_connections}</dd>
            <dt>sinapses</dt>
            <dd className="mono">{summary.n_synapses}</dd>
            <dt>limiar de sinapses</dt>
            <dd className="mono">
              {summary.synapse_threshold ?? 'não disponível'}
            </dd>
            <dt>snapshot de conectividade</dt>
            <dd className="mono">
              {connectivity ? (
                <a
                  className="link"
                  href={connectivity.url}
                  target="_blank"
                  rel="noreferrer noopener"
                >
                  v{connectivity.version} · {connectivity.license} ↗
                </a>
              ) : (
                'não disponível'
              )}
            </dd>
            <dt>anotações</dt>
            <dd className="mono">
              {annotations ? (
                <a
                  className="link"
                  href={annotations.url}
                  target="_blank"
                  rel="noreferrer noopener"
                >
                  {annotations.repo} {annotations.tag} ↗
                </a>
              ) : (
                'não disponível'
              )}
            </dd>
            <dt>espaço de coordenadas</dt>
            <dd>{summary.coordinate_space.space}</dd>
          </dl>

          <h3 className="notice__subheading">Regra excitatório / inibitório</h3>
          <p className="notice__text">
            <span className="tag mono">{summary.nt_policy}</span>{' '}
            {summary.nt_policy_note ?? 'não disponível'}
          </p>

          <h3 className="notice__subheading">Licenciamento</h3>
          <ul className="notice__list">
            {summary.licensing.map((item) => (
              <li key={item}>{item}</li>
            ))}
          </ul>
        </article>

        <article className="notice__card">
          <h3>Como citar</h3>
          <ul className="notice__citations">
            {summary.citations.map((citation) => (
              <li key={citation}>
                <Citation text={citation} />
              </li>
            ))}
          </ul>
          <p className="notice__text">
            Explorador oficial do conjunto de dados:{' '}
            <a
              className="link"
              href={FLYWIRE_URL}
              target="_blank"
              rel="noreferrer noopener"
            >
              codex.flywire.ai ↗
            </a>
          </p>
        </article>
      </div>
    </section>
  );
}

/** Renders a citation string, turning its trailing DOI URL into a link. */
function Citation({ text }: { text: string }) {
  const match = text.match(/(https?:\/\/\S+)$/);
  if (!match) return <span>{text}</span>;
  const url = match[1];
  return (
    <span>
      {text.slice(0, match.index)}
      <a className="link" href={url} target="_blank" rel="noreferrer noopener">
        {url}
      </a>
    </span>
  );
}
