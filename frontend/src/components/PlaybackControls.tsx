import type { MaterialisedFrame } from '../api/protocol';
import { SPEED_OPTIONS, type Playback, type PlaybackSpeed } from '../state/usePlayback';

export interface PlaybackControlsProps {
  playback: Playback;
  frames: MaterialisedFrame[];
  /** Total frames the run will produce (header.n_frames), if known. */
  expectedFrames: number | null;
  isStreaming: boolean;
  hasRun: boolean;
  onRerun: () => void;
  canRerun: boolean;
}

export function PlaybackControls({
  playback,
  frames,
  expectedFrames,
  isStreaming,
  hasRun,
  onRerun,
  canRerun,
}: PlaybackControlsProps) {
  const lastIndex = Math.max(0, frames.length - 1);
  const current = frames[playback.step] ?? null;
  const disabled = frames.length === 0;

  return (
    <div className="playback">
      <div className="playback__buttons">
        <button
          type="button"
          className="btn btn--icon"
          onClick={playback.replay}
          disabled={disabled}
          title="Voltar ao passo 0 e reproduzir de novo"
          aria-label="Reproduzir do início"
        >
          ⟲
        </button>
        <button
          type="button"
          className="btn btn--icon"
          onClick={playback.stepBack}
          disabled={disabled || playback.step === 0}
          aria-label="Passo anterior"
        >
          ◀
        </button>
        <button
          type="button"
          className="btn btn--primary btn--icon btn--icon-lg"
          onClick={playback.toggle}
          disabled={disabled}
          aria-label={playback.isPlaying ? 'Pausar' : 'Reproduzir'}
        >
          {playback.isPlaying ? '❚❚' : '▶'}
        </button>
        <button
          type="button"
          className="btn btn--icon"
          onClick={playback.stepForward}
          disabled={disabled || playback.step >= lastIndex}
          aria-label="Próximo passo"
        >
          ▶
        </button>
      </div>

      <div className="playback__scrub">
        <input
          type="range"
          min={0}
          max={lastIndex}
          step={1}
          value={Math.min(playback.step, lastIndex)}
          disabled={disabled}
          onChange={(event) => playback.seek(Number(event.target.value))}
          aria-label="Passo da simulação"
        />
        <div className="playback__readout" aria-live="polite">
          <span className="playback__step mono" data-testid="playback-step">
            passo {playback.step}
            <span className="playback__step-total">
              {' / '}
              {expectedFrames ? expectedFrames - 1 : lastIndex}
            </span>
          </span>
          {current && (
            <span className="playback__stats mono">
              {current.summary.n_spiked} disparando · ativação média{' '}
              {current.summary.mean_activation.toFixed(3)}
            </span>
          )}
          {!hasRun && <span className="playback__stats">nenhuma simulação executada ainda</span>}
          {isStreaming && (
            <span className="playback__badge playback__badge--live">
              recebendo passos… {frames.length}
              {expectedFrames ? `/${expectedFrames}` : ''}
            </span>
          )}
          {playback.waiting && isStreaming && (
            <span className="playback__badge">aguardando o próximo passo</span>
          )}
        </div>
      </div>

      <div className="playback__right">
        <label className="field field--inline">
          <span className="label label--tight">velocidade</span>
          <select
            className="input input--sm"
            value={playback.speed}
            onChange={(event) =>
              playback.setSpeed(Number(event.target.value) as PlaybackSpeed)
            }
          >
            {SPEED_OPTIONS.map((option) => (
              <option key={option} value={option}>
                {option} passos/s
              </option>
            ))}
          </select>
        </label>
        <button
          type="button"
          className="btn btn--ghost btn--sm"
          onClick={onRerun}
          disabled={!canRerun}
          title="Executar a simulação de novo com os parâmetros atuais"
        >
          Rodar de novo
        </button>
      </div>
    </div>
  );
}
