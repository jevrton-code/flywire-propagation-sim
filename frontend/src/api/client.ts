import type {
  CellTypeListResponse,
  GraphResponse,
  ModelDefaultsResponse,
  NtPolicy,
  ProvenanceResponse,
} from './types';

/**
 * REST access to the FastAPI backend.
 *
 * In development Vite proxies `/api` and `/ws` to `http://127.0.0.1:8000`, so
 * everything is same-origin and the base URL is simply the empty string. Set
 * `VITE_API_BASE` to point a production build at a different host.
 */
const BASE = (import.meta.env?.VITE_API_BASE ?? '').replace(/\/$/, '');

/** An API failure carrying the backend's stable `code`, not just a status. */
export class ApiError extends Error {
  readonly code: string;
  readonly status: number;
  readonly details: Record<string, unknown> | null;

  constructor(
    code: string,
    message: string,
    status: number,
    details: Record<string, unknown> | null = null,
  ) {
    super(message);
    this.name = 'ApiError';
    this.code = code;
    this.status = status;
    this.details = details;
  }
}

export interface CircuitQuery {
  circuit?: string;
  nt_policy?: NtPolicy;
}

function withQuery(path: string, query: CircuitQuery = {}): string {
  const params = new URLSearchParams();
  if (query.circuit) params.set('circuit', query.circuit);
  if (query.nt_policy) params.set('nt_policy', query.nt_policy);
  const qs = params.toString();
  return `${BASE}${path}${qs ? `?${qs}` : ''}`;
}

async function getJson<T>(url: string, signal?: AbortSignal): Promise<T> {
  let response: Response;
  try {
    response = await fetch(url, { signal, headers: { Accept: 'application/json' } });
  } catch (cause) {
    // Distinguishing "server is down" from "server said no" matters for the
    // message we show: one is "start the backend", the other is a real API error.
    if (signal?.aborted) throw cause;
    throw new ApiError(
      'network_unreachable',
      `não foi possível falar com a API em ${url || 'mesma origem'}. ` +
        'O backend está rodando? (python -m flywire_api.run)',
      0,
    );
  }

  if (!response.ok) {
    let code = `http_${response.status}`;
    let message = `a API respondeu ${response.status} ${response.statusText}`;
    let details: Record<string, unknown> | null = null;
    try {
      const body = await response.json();
      if (body?.error) {
        code = body.error.code ?? code;
        message = body.error.message ?? message;
        details = body.error.details ?? null;
      }
    } catch {
      /* a non-JSON error body is not worth failing over; keep the status text */
    }
    throw new ApiError(code, message, response.status, details);
  }

  return (await response.json()) as T;
}

/** Nodes + edges + provenance for the whole subgraph, in one round trip. */
export function fetchGraph(query?: CircuitQuery, signal?: AbortSignal): Promise<GraphResponse> {
  return getJson<GraphResponse>(withQuery('/api/circuit/graph', query), signal);
}

/** Cell types with counts, plus the backend's ready-made stimulus presets. */
export function fetchCellTypes(
  query?: CircuitQuery,
  signal?: AbortSignal,
): Promise<CellTypeListResponse> {
  return getJson<CellTypeListResponse>(withQuery('/api/circuit/cell-types', query), signal);
}

/** Dataset provenance: snapshot version, DOIs, licences, citations. */
export function fetchProvenance(
  query?: CircuitQuery,
  signal?: AbortSignal,
): Promise<ProvenanceResponse> {
  return getJson<ProvenanceResponse>(withQuery('/api/circuit/provenance', query), signal);
}

/** Default LIF parameters and the server's hard limits. */
export function fetchModelDefaults(signal?: AbortSignal): Promise<ModelDefaultsResponse> {
  return getJson<ModelDefaultsResponse>(withQuery('/api/model/defaults'), signal);
}

/** Absolute ws:// URL for the streaming endpoint, derived from the page origin. */
export function simulationSocketUrl(): string {
  if (BASE) return BASE.replace(/^http/, 'ws') + '/ws/simulate';
  const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
  return `${protocol}//${window.location.host}/ws/simulate`;
}
