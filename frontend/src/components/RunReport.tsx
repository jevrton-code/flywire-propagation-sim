import type { RunStatus } from '../api/protocol';
import type { SimulationReport } from '../api/types';

export interface RunReportProps {
  report: SimulationReport | null;
  status: RunStatus;
  cancelledAtStep: number | null;
}

const STATUS_LABELS: Partial<Record<RunStatus, string>> = {
  streaming: 'em execução',
  complete: 'concluída',
  cancelled: 'interrompida',
  failed: 'falhou',
};

export function RunReport({ report, status, cancelledAtStep }: RunReportProps) {
  return (
    <section className="panel" aria-labelledby="report-heading">
      <h2 id="report-heading" className="panel__heading">
        Resultado da execução
        {STATUS_LABELS[status] && (
          <span className={`tag tag--sm tag--${status}`}>{STATUS_LABELS[status]}</span>
        )}
      </h2>

      {!report && (
        <p className="hint hint--empty">
          O relatório aparece quando a simulação termina (ou é interrompida).
        </p>
      )}

      {report && (
        <>
          {!report.numerically_finite && (
            <p className="tag tag--danger">
              A execução produziu NaN/infinito: o resultado deve ser considerado
              inválido.
            </p>
          )}
          {cancelledAtStep !== null && (
            <p className="hint hint--warn">
              Interrompida no passo {cancelledAtStep}; o relatório cobre apenas os
              passos executados.
            </p>
          )}

          <dl className="kv">
            <dt>passos</dt>
            <dd className="mono">{report.steps}</dd>
            <dt>estimulados</dt>
            <dd className="mono">{report.stimulated_neurons}</dd>
            <dt>dispararam</dt>
            <dd className="mono">
              {report.neurons_that_fired} / {report.neurons}
            </dd>
            <dt>a jusante</dt>
            <dd className="mono">{report.downstream_neurons_that_fired}</dd>
            <dt>circuito recrutado</dt>
            <dd className="mono">
              {(report.fraction_of_circuit_recruited * 100).toFixed(1)}%
            </dd>
            <dt>disparos totais</dt>
            <dd className="mono">{report.total_spikes}</dd>
            <dt>pico</dt>
            <dd className="mono">
              {report.peak_step === null
                ? 'não disponível'
                : `passo ${report.peak_step} · ${report.peak_n_spiked} disparando`}
            </dd>
          </dl>

          <h3 className="panel__subheading">Primeiro disparo por tipo celular</h3>
          {Object.keys(report.first_spike_step_by_cell_type).length === 0 ? (
            <p className="hint hint--empty">Nenhum tipo celular disparou nesta execução.</p>
          ) : (
            <ul className="firstspike">
              {Object.entries(report.first_spike_step_by_cell_type)
                .sort((a, b) => a[1] - b[1])
                .map(([cellType, step]) => (
                  <li key={cellType}>
                    <span>{cellType}</span>
                    <span className="firstspike__step mono">passo {step}</span>
                    <span className="firstspike__count mono">
                      {report.neurons_fired_by_cell_type[cellType] ?? 0} neurônios
                    </span>
                  </li>
                ))}
            </ul>
          )}
        </>
      )}
    </section>
  );
}
