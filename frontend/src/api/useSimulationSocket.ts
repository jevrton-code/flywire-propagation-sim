import { useCallback, useEffect, useReducer, useRef } from 'react';
import { simulationSocketUrl } from './client';
import { initialRunState, runReducer, type RunState } from './protocol';
import type { SimulationRequest } from './types';

/**
 * Owns the lifetime of the `/ws/simulate` connection.
 *
 * The socket is opened lazily on the first run and then *reused*: the backend
 * keeps the connection open even after a rejected request, so a user who
 * mistyped a parameter can fix it and press run again without a reconnect
 * round trip. A run is only started once the socket is actually open, so
 * `start()` queues the request when it is called on a connecting socket.
 */
export interface SimulationSocket {
  state: RunState;
  /** Open the socket if needed and start a run (or queue it until open). */
  start: (request: SimulationRequest) => void;
  /** Ask the server to stop the run in progress; a partial report follows. */
  cancel: () => void;
  /** Drop frames and report, keeping the connection. */
  reset: () => void;
  /** Close the socket (used on unmount, and by the "reconnect" affordance). */
  disconnect: () => void;
}

export function useSimulationSocket(): SimulationSocket {
  const [state, dispatch] = useReducer(runReducer, initialRunState);
  const socketRef = useRef<WebSocket | null>(null);
  const pendingRef = useRef<SimulationRequest | null>(null);
  const unmountedRef = useRef(false);

  useEffect(() => {
    unmountedRef.current = false;
    return () => {
      unmountedRef.current = true;
      socketRef.current?.close();
      socketRef.current = null;
    };
  }, []);

  const send = useCallback((payload: unknown) => {
    const socket = socketRef.current;
    if (socket && socket.readyState === WebSocket.OPEN) {
      socket.send(JSON.stringify(payload));
      return true;
    }
    return false;
  }, []);

  const open = useCallback(() => {
    dispatch({ kind: 'connecting' });

    let socket: WebSocket;
    try {
      socket = new WebSocket(simulationSocketUrl());
    } catch (cause) {
      dispatch({
        kind: 'socket-error',
        message:
          'não foi possível abrir a conexão WebSocket: ' +
          (cause instanceof Error ? cause.message : String(cause)),
      });
      return;
    }
    socketRef.current = socket;

    socket.onopen = () => {
      if (unmountedRef.current) return;
      dispatch({ kind: 'socket-open' });
      const queued = pendingRef.current;
      if (queued) {
        pendingRef.current = null;
        dispatch({ kind: 'start-requested' });
        socket.send(JSON.stringify({ action: 'start', request: queued }));
      }
    };

    socket.onmessage = (event: MessageEvent) => {
      if (unmountedRef.current) return;
      dispatch({ kind: 'server-message', raw: event.data });
    };

    // The browser gives no useful detail on a WebSocket `error` event (by
    // design, to avoid leaking cross-origin information), so the message here
    // is the actionable guess rather than a transcription of the event.
    socket.onerror = () => {
      if (unmountedRef.current) return;
      pendingRef.current = null;
      dispatch({ kind: 'socket-error' });
    };

    socket.onclose = (event: CloseEvent) => {
      if (unmountedRef.current) return;
      if (socketRef.current === socket) socketRef.current = null;
      pendingRef.current = null;
      dispatch({ kind: 'socket-closed', clean: event.wasClean });
    };
  }, []);

  const start = useCallback(
    (request: SimulationRequest) => {
      const socket = socketRef.current;
      if (socket && socket.readyState === WebSocket.OPEN) {
        dispatch({ kind: 'start-requested' });
        send({ action: 'start', request });
        return;
      }
      pendingRef.current = request;
      if (!socket || socket.readyState === WebSocket.CLOSING || socket.readyState === WebSocket.CLOSED) {
        open();
      }
      // A CONNECTING socket will pick the request up in `onopen`.
    },
    [open, send],
  );

  const cancel = useCallback(() => {
    pendingRef.current = null;
    send({ action: 'cancel' });
  }, [send]);

  const reset = useCallback(() => dispatch({ kind: 'reset' }), []);

  const disconnect = useCallback(() => {
    pendingRef.current = null;
    socketRef.current?.close();
    socketRef.current = null;
  }, []);

  return { state, start, cancel, reset, disconnect };
}
