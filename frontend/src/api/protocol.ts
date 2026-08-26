/**
 * Pure logic for the `/ws/simulate` protocol: parsing server messages and
 * folding them into the state the UI animates.
 *
 * Everything here is deliberately free of WebSocket, React and timers so it can
 * be unit-tested directly. `useSimulationSocket` is the thin, effectful shell
 * that feeds this reducer.
 *
 * Frames are materialised into typed arrays aligned to `header.neuron_ids`.
 * Delta frames are folded against the previous frame here, so the rest of the
 * app only ever sees complete per-step vectors and does not need to know which
 * `frame_format` was requested.
 */

import type {
  FrameMessage,
  HeaderMessage,
  ServerMessage,
  SimulationReport,
  StepSummary,
} from './types';

/** One time step, fully materialised: every array has `n_neurons` entries. */
export interface MaterialisedFrame {
  step: number;
  /** Exponentially filtered spike trace in [0, 1] — the display signal. */
  activation: Float32Array;
  /** 1 where the neuron spiked on this step. */
  spiked: Uint8Array;
  membrane: Float32Array | null;
  summary: StepSummary;
}

export type ConnectionStatus = 'idle' | 'connecting' | 'open' | 'closed' | 'failed';
export type RunStatus = 'idle' | 'starting' | 'streaming' | 'complete' | 'cancelled' | 'failed';

export interface RunError {
  code: string;
  message: string;
  details?: Record<string, unknown> | null;
}

export interface RunState {
  connection: ConnectionStatus;
  run: RunStatus;
  header: HeaderMessage | null;
  frames: MaterialisedFrame[];
  report: SimulationReport | null;
  /** Step at which a cancelled run stopped, if it was cancelled. */
  cancelledAtStep: number | null;
  error: RunError | null;
  /** Non-fatal notices (e.g. a message shape we did not recognise). */
  notice: string | null;
}

export const initialRunState: RunState = {
  connection: 'idle',
  run: 'idle',
  header: null,
  frames: [],
  report: null,
  cancelledAtStep: null,
  error: null,
  notice: null,
};

// --------------------------------------------------------------------------- //
// Parsing
// --------------------------------------------------------------------------- //

export type ParseResult =
  | { ok: true; message: ServerMessage }
  | { ok: false; reason: string };

const KNOWN_TYPES = new Set([
  'ready',
  'header',
  'frame',
  'complete',
  'cancelled',
  'error',
]);

/**
 * Turn a raw socket payload into a typed server message.
 *
 * Never throws: a malformed payload is a condition the UI has to show, not an
 * exception that kills the socket handler.
 */
export function parseServerMessage(raw: unknown): ParseResult {
  if (typeof raw !== 'string') {
    return { ok: false, reason: 'a mensagem recebida não é texto JSON' };
  }
  let payload: unknown;
  try {
    payload = JSON.parse(raw);
  } catch {
    return { ok: false, reason: 'a mensagem recebida não é JSON válido' };
  }
  if (typeof payload !== 'object' || payload === null || Array.isArray(payload)) {
    return { ok: false, reason: 'a mensagem recebida não é um objeto JSON' };
  }
  const type = (payload as { type?: unknown }).type;
  if (typeof type !== 'string' || !KNOWN_TYPES.has(type)) {
    return { ok: false, reason: `tipo de mensagem desconhecido: ${JSON.stringify(type)}` };
  }
  return { ok: true, message: payload as ServerMessage };
}

// --------------------------------------------------------------------------- //
// Frame materialisation
// --------------------------------------------------------------------------- //

/**
 * Expand one frame message into full per-neuron arrays.
 *
 * @param message  the frame as it came off the wire (dense or delta)
 * @param previous the previous materialised frame, required for delta frames
 * @param nNeurons length of every per-neuron array, from the header
 * @throws Error when a delta frame arrives with no baseline to apply it to
 */
export function materialiseFrame(
  message: FrameMessage,
  previous: MaterialisedFrame | null,
  nNeurons: number,
): MaterialisedFrame {
  if (message.format === 'dense') {
    const membrane =
      message.membrane != null ? Float32Array.from(message.membrane) : null;
    const spiked = new Uint8Array(nNeurons);
    for (let i = 0; i < message.spiked.length && i < nNeurons; i += 1) {
      spiked[i] = message.spiked[i] ? 1 : 0;
    }
    return {
      step: message.step,
      activation: Float32Array.from(message.activation),
      spiked,
      membrane,
      summary: message.summary,
    };
  }

  if (previous === null) {
    throw new Error(
      `frame delta no passo ${message.step} sem um frame anterior para aplicar; ` +
        'o servidor deveria enviar o passo 0 em formato dense',
    );
  }

  const activation = Float32Array.from(previous.activation);
  applySparse(activation, message.activation);

  let membrane: Float32Array | null = null;
  if (previous.membrane) {
    membrane = Float32Array.from(previous.membrane);
    if (message.membrane) applySparse(membrane, message.membrane);
  }

  // `spiked` is not a diff: it is the complete set of indices spiking now.
  const spiked = new Uint8Array(nNeurons);
  for (const index of message.spiked) {
    if (index >= 0 && index < nNeurons) spiked[index] = 1;
  }

  return { step: message.step, activation, spiked, membrane, summary: message.summary };
}

function applySparse(
  target: Float32Array,
  sparse: { indices: number[]; values: number[] },
): void {
  const { indices, values } = sparse;
  for (let k = 0; k < indices.length; k += 1) {
    const index = indices[k];
    if (index >= 0 && index < target.length) target[index] = values[k];
  }
}

// --------------------------------------------------------------------------- //
// Reducer
// --------------------------------------------------------------------------- //

export type RunEvent =
  | { kind: 'connecting' }
  | { kind: 'socket-open' }
  | { kind: 'socket-closed'; clean: boolean }
  | { kind: 'socket-error'; message?: string }
  | { kind: 'start-requested' }
  | { kind: 'server-message'; raw: unknown }
  | { kind: 'dismiss-notice' }
  | { kind: 'reset' };

/**
 * Fold one event into the run state.
 *
 * Deliberately tolerant: an `error` message does *not* close the socket on the
 * server side, so it must not put the client into a dead state either — the
 * user fixes the form and runs again on the same connection.
 */
export function runReducer(state: RunState, event: RunEvent): RunState {
  switch (event.kind) {
    case 'connecting':
      return { ...initialRunState, connection: 'connecting' };

    case 'socket-open':
      return { ...state, connection: 'open', error: null };

    case 'socket-closed':
      return {
        ...state,
        connection: state.connection === 'failed' ? 'failed' : 'closed',
        // A socket that dies mid-stream leaves a partial run: say so instead of
        // leaving a spinner that never resolves.
        run: state.run === 'streaming' || state.run === 'starting' ? 'failed' : state.run,
        error:
          state.error ??
          (state.run === 'streaming' || state.run === 'starting'
            ? {
                code: 'connection_lost',
                message: event.clean
                  ? 'a conexão foi encerrada antes do fim da simulação.'
                  : 'a conexão com o servidor caiu durante a simulação.',
              }
            : null),
      };

    case 'socket-error':
      return {
        ...state,
        connection: 'failed',
        run: state.run === 'streaming' || state.run === 'starting' ? 'failed' : state.run,
        error: {
          code: 'connection_failed',
          message:
            event.message ??
            'não foi possível manter a conexão WebSocket com o servidor. ' +
              'Verifique se o backend está rodando e tente novamente.',
        },
      };

    case 'start-requested':
      return {
        ...state,
        run: 'starting',
        header: null,
        frames: [],
        report: null,
        cancelledAtStep: null,
        error: null,
      };

    case 'dismiss-notice':
      return { ...state, notice: null };

    case 'reset':
      return { ...initialRunState, connection: state.connection };

    case 'server-message':
      return applyServerMessage(state, event.raw);
  }
}

function applyServerMessage(state: RunState, raw: unknown): RunState {
  const parsed = parseServerMessage(raw);
  if (!parsed.ok) {
    return { ...state, notice: parsed.reason };
  }
  const message = parsed.message;

  switch (message.type) {
    case 'ready':
      return { ...state, connection: 'open' };

    case 'header':
      return {
        ...state,
        run: 'streaming',
        header: message,
        frames: [],
        report: null,
        cancelledAtStep: null,
        error: null,
      };

    case 'frame': {
      if (!state.header) {
        return { ...state, notice: 'frame recebido antes do cabeçalho da simulação' };
      }
      const previous = state.frames.length ? state.frames[state.frames.length - 1] : null;
      let frame: MaterialisedFrame;
      try {
        frame = materialiseFrame(message, previous, state.header.n_neurons);
      } catch (cause) {
        return {
          ...state,
          run: 'failed',
          error: {
            code: 'frame_decode_failed',
            message: cause instanceof Error ? cause.message : String(cause),
          },
        };
      }
      return { ...state, run: 'streaming', frames: [...state.frames, frame] };
    }

    case 'complete':
      return { ...state, run: 'complete', report: message.report };

    case 'cancelled':
      return {
        ...state,
        run: 'cancelled',
        report: message.report,
        cancelledAtStep: message.step,
      };

    case 'error':
      // A cancel that lost the race against the last frame is not a failure
      // the user needs to see in red: on a fast link a 200-step run finishes in
      // well under a second, so clicking "stop" just as it ends is routine.
      if (message.error?.code === 'nothing_to_cancel') {
        return state.run === 'streaming' || state.run === 'starting'
          ? { ...state, notice: message.error.message }
          : state;
      }
      return {
        ...state,
        // The socket stays open on the server side, so the run — not the
        // connection — is what failed. The user can correct and retry.
        run: state.run === 'streaming' || state.run === 'starting' ? 'failed' : state.run,
        error: {
          code: message.error?.code ?? 'unknown_error',
          message: message.error?.message ?? 'o servidor recusou a requisição.',
          details: message.error?.details ?? null,
        },
      };
  }
}
