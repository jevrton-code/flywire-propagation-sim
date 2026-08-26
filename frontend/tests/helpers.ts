import { vi } from 'vitest';
import { CELL_TYPES, GRAPH, MODEL_DEFAULTS, PROVENANCE } from './fixtures';

/**
 * Routes the four REST calls the app makes on boot to fixtures.
 * `overrides` can replace a body or force a failure for one endpoint.
 */
export function mockApi(
  overrides: Partial<Record<'graph' | 'cellTypes' | 'provenance' | 'defaults', unknown>> = {},
) {
  const fetchMock = vi.fn(async (input: RequestInfo | URL) => {
    const url = String(input);
    const pick = () => {
      if (url.includes('/circuit/graph')) return overrides.graph ?? GRAPH;
      if (url.includes('/circuit/cell-types')) return overrides.cellTypes ?? CELL_TYPES;
      if (url.includes('/circuit/provenance')) return overrides.provenance ?? PROVENANCE;
      if (url.includes('/model/defaults')) return overrides.defaults ?? MODEL_DEFAULTS;
      return null;
    };
    const body = pick();
    if (body instanceof Error) throw body;
    if (body === null) {
      return new Response(JSON.stringify({ error: { code: 'not_found', message: 'no' } }), {
        status: 404,
        headers: { 'content-type': 'application/json' },
      });
    }
    return new Response(JSON.stringify(body), {
      status: 200,
      headers: { 'content-type': 'application/json' },
    });
  });
  vi.stubGlobal('fetch', fetchMock);
  return fetchMock;
}

/** A controllable WebSocket stand-in. Tests drive it from the "server" side. */
export class FakeWebSocket {
  static instances: FakeWebSocket[] = [];
  static CONNECTING = 0;
  static OPEN = 1;
  static CLOSING = 2;
  static CLOSED = 3;

  readonly url: string;
  readyState = FakeWebSocket.CONNECTING;
  sent: string[] = [];

  onopen: ((event: Event) => void) | null = null;
  onmessage: ((event: MessageEvent) => void) | null = null;
  onerror: ((event: Event) => void) | null = null;
  onclose: ((event: CloseEvent) => void) | null = null;

  constructor(url: string) {
    this.url = url;
    FakeWebSocket.instances.push(this);
  }

  send(data: string) {
    this.sent.push(data);
  }

  close() {
    this.readyState = FakeWebSocket.CLOSED;
    this.onclose?.({ wasClean: true } as CloseEvent);
  }

  // --- server-side controls ------------------------------------------------
  open() {
    this.readyState = FakeWebSocket.OPEN;
    this.onopen?.(new Event('open'));
  }

  emit(message: unknown) {
    this.onmessage?.({ data: JSON.stringify(message) } as MessageEvent);
  }

  emitRaw(data: unknown) {
    this.onmessage?.({ data } as MessageEvent);
  }

  fail() {
    this.onerror?.(new Event('error'));
  }

  drop() {
    this.readyState = FakeWebSocket.CLOSED;
    this.onclose?.({ wasClean: false } as CloseEvent);
  }

  /** Parsed messages the client sent. */
  get commands(): Array<Record<string, unknown>> {
    return this.sent.map((raw) => JSON.parse(raw));
  }

  static latest(): FakeWebSocket {
    const socket = FakeWebSocket.instances[FakeWebSocket.instances.length - 1];
    if (!socket) throw new Error('nenhum WebSocket foi aberto');
    return socket;
  }

  static reset() {
    FakeWebSocket.instances = [];
  }
}

export function mockWebSocket() {
  FakeWebSocket.reset();
  vi.stubGlobal('WebSocket', FakeWebSocket);
  return FakeWebSocket;
}
