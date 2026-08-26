import type { RunError } from '../api/protocol';

export type BannerTone = 'error' | 'warning' | 'info';

export interface StatusBannerProps {
  tone: BannerTone;
  title: string;
  message: string;
  details?: Record<string, unknown> | null;
  actionLabel?: string;
  onAction?: () => void;
  onDismiss?: () => void;
}

/**
 * Failures are shown here, in the layout, never only in the console.
 *
 * `role="alert"` (not `status`) for errors so a screen reader interrupts:
 * a dropped socket means the animation on screen is stale, which the user has
 * to know immediately.
 */
export function StatusBanner({
  tone,
  title,
  message,
  details,
  actionLabel,
  onAction,
  onDismiss,
}: StatusBannerProps) {
  return (
    <div
      className={`banner banner--${tone}`}
      role={tone === 'error' ? 'alert' : 'status'}
      aria-live={tone === 'error' ? 'assertive' : 'polite'}
    >
      <div className="banner__body">
        <p className="banner__title">{title}</p>
        <p className="banner__message">{message}</p>
        {details && Object.keys(details).length > 0 && (
          <details className="banner__details">
            <summary>detalhes técnicos</summary>
            <pre>{JSON.stringify(details, null, 2)}</pre>
          </details>
        )}
      </div>
      <div className="banner__actions">
        {actionLabel && onAction && (
          <button type="button" className="btn btn--ghost btn--sm" onClick={onAction}>
            {actionLabel}
          </button>
        )}
        {onDismiss && (
          <button
            type="button"
            className="btn btn--icon"
            onClick={onDismiss}
            aria-label="Dispensar aviso"
          >
            ×
          </button>
        )}
      </div>
    </div>
  );
}

/** Maps a run error to the banner copy, including what the user can do next. */
export function errorBannerCopy(error: RunError): { title: string; message: string } {
  switch (error.code) {
    case 'connection_failed':
      return {
        title: 'Sem conexão com o servidor de simulação',
        message:
          `${error.message} Confira se o backend está rodando ` +
          '(python -m flywire_api.run) e clique em "Tentar de novo".',
      };
    case 'connection_lost':
      return {
        title: 'A conexão caiu durante a simulação',
        message: `${error.message} Os passos já recebidos continuam disponíveis para reprodução.`,
      };
    case 'simulation_in_progress':
      return {
        title: 'Já existe uma simulação rodando',
        message: `${error.message}`,
      };
    case 'frame_decode_failed':
      return {
        title: 'Não foi possível decodificar um passo da simulação',
        message: error.message,
      };
    default:
      return { title: `O servidor recusou a requisição (${error.code})`, message: error.message };
  }
}
