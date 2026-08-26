import { act, render, screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import App from '../src/App';
import { CELL_TYPES, denseFrame, GRAPH, headerMessage, REPORT, SUMMARY } from './fixtures';
import { FakeWebSocket, mockApi, mockWebSocket } from './helpers';

const N = GRAPH.neurons.length;
const rest = (values: number[]) => values;

async function boot() {
  render(<App />);
  await screen.findByRole('heading', { name: /Propagação de ativação/i });
  await waitFor(() => expect(screen.getByTestId('force-graph')).toBeInTheDocument());
}

/** Opens the socket and plays a two-step run from the "server" side. */
async function streamARun(frames = 3) {
  const socket = FakeWebSocket.latest();
  await act(async () => {
    socket.open();
    socket.emit({ type: 'ready', protocol_version: 1, limits: {} });
  });
  await act(async () => {
    socket.emit(headerMessage({ n_steps: frames - 1, n_frames: frames }));
  });
  for (let step = 0; step < frames; step += 1) {
    const activation = rest(GRAPH.neurons.map((_, i) => (i === 2 ? step / frames : 0)));
    const spiked = GRAPH.neurons.map((_, i) => i === 2 && step > 0);
    await act(async () => socket.emit(denseFrame(step, activation, spiked)));
  }
  return socket;
}

describe('App', () => {
  beforeEach(() => {
    mockApi();
    mockWebSocket();
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it('shows a loading state and then draws the circuit it fetched', async () => {
    render(<App />);
    expect(screen.getByText(/Carregando o subgrafo do conectoma/i)).toBeInTheDocument();

    const graph = await screen.findByTestId('force-graph');
    expect(graph).toHaveAttribute('data-node-count', String(N));
    expect(graph).toHaveAttribute('data-link-count', String(GRAPH.edges.length));
    // The node ids handed to the renderer are the API's strings, unparsed.
    const nodes = screen.getAllByTestId('graph-node');
    expect(nodes.map((n) => n.dataset.rootId)).toEqual(
      GRAPH.neurons.map((n) => n.root_id),
    );
  });

  it('shows the disclaimer and every simplification without any interaction', async () => {
    await boot();

    expect(screen.getByText(/Conectoma real, dinâmica de brinquedo/i)).toBeInTheDocument();
    expect(screen.getByText(SUMMARY.disclaimer)).toBeVisible();
    for (const item of SUMMARY.simplifications) {
      expect(screen.getByText(item)).toBeVisible();
    }
    expect(
      screen.getByText(/Dorkenwald, S\., Matsliah, A\., Sterling, A\.R\./),
    ).toBeVisible();
    expect(
      screen.getAllByRole('link', { name: /codex\.flywire\.ai/ })[0],
    ).toHaveAttribute('href', 'https://codex.flywire.ai');
  });

  it('reports the real counts from the API rather than hardcoded ones', async () => {
    await boot();
    const bar = screen.getByText(/Conectoma real, dinâmica de brinquedo/i).parentElement!;
    expect(bar).toHaveTextContent('5 neurônios');
    expect(bar).toHaveTextContent('3 conexões');
    expect(bar).toHaveTextContent('v783.0');
  });

  it('sends the preset the backend gave it when the user runs a simulation', async () => {
    const user = userEvent.setup();
    await boot();

    await user.click(screen.getByRole('radio', { name: /EPG population/ }));
    await user.click(screen.getByRole('button', { name: /Injetar estímulo e simular/ }));

    const socket = FakeWebSocket.latest();
    await act(async () => socket.open());

    const start = socket.commands.find((c) => c.action === 'start');
    expect(start).toBeDefined();
    const request = start!.request as Record<string, unknown>;
    expect(request.source).toEqual(CELL_TYPES.presets[0].source);
    expect(request.steps).toBe(40);
    expect(request.frame_format).toBe('dense');
  });

  it('animates from the first frame instead of waiting for the whole run', async () => {
    const user = userEvent.setup();
    await boot();
    await user.click(screen.getByRole('radio', { name: /EPG population/ }));
    await user.click(screen.getByRole('button', { name: /Injetar estímulo e simular/ }));

    const socket = FakeWebSocket.latest();
    await act(async () => {
      socket.open();
      socket.emit({ type: 'ready', protocol_version: 1, limits: {} });
      socket.emit(headerMessage({ n_steps: 40, n_frames: 41 }));
    });

    // One frame in and the UI is already showing a step out of 40 — nothing
    // waits for `complete`.
    await act(async () =>
      socket.emit(denseFrame(0, GRAPH.neurons.map(() => 0), GRAPH.neurons.map(() => false))),
    );
    expect(screen.getByTestId('playback-step').textContent).toMatch(/passo 0\s*\/\s*40/);
    expect(screen.getByText(/recebendo passos/)).toBeInTheDocument();
  });

  it('renders the final report from the run', async () => {
    const user = userEvent.setup();
    await boot();
    await user.click(screen.getByRole('radio', { name: /EPG population/ }));
    await user.click(screen.getByRole('button', { name: /Injetar estímulo e simular/ }));

    const socket = await streamARun();
    await act(async () => socket.emit({ type: 'complete', report: REPORT }));

    const report = screen.getByRole('region', { name: /Resultado da execução/i });
    expect(within(report).getByText('60.0%')).toBeInTheDocument();
    expect(within(report).getByText(/EPG/)).toBeInTheDocument();
    expect(within(report).getByText('passo 1')).toBeInTheDocument();
  });

  it('offers cancel while a run is streaming and shows the partial report', async () => {
    const user = userEvent.setup();
    await boot();
    await user.click(screen.getByRole('radio', { name: /EPG population/ }));
    await user.click(screen.getByRole('button', { name: /Injetar estímulo e simular/ }));

    const socket = await streamARun();
    const cancel = screen.getByRole('button', { name: /Interromper simulação/ });
    await user.click(cancel);
    expect(socket.commands.at(-1)).toEqual({ action: 'cancel' });

    await act(async () => socket.emit({ type: 'cancelled', step: 2, report: REPORT }));
    expect(screen.getByText(/Interrompida no passo 2/)).toBeInTheDocument();
  });

  it('shows a server rejection in the interface and lets the user retry', async () => {
    const user = userEvent.setup();
    await boot();
    await user.click(screen.getByRole('radio', { name: /EPG population/ }));
    await user.click(screen.getByRole('button', { name: /Injetar estímulo e simular/ }));

    const socket = FakeWebSocket.latest();
    await act(async () => {
      socket.open();
      socket.emit({
        type: 'error',
        status: 422,
        error: {
          code: 'unknown_cell_type',
          message: "unknown cell_type(s) ['EPGx']",
          details: { received: ['EPGx'] },
        },
      });
    });

    const alert = await screen.findByRole('alert');
    expect(alert).toHaveTextContent('unknown_cell_type');
    expect(alert).toHaveTextContent("unknown cell_type(s) ['EPGx']");

    // The socket stayed open, so retrying reuses it rather than reconnecting.
    await user.click(within(alert).getByRole('button', { name: /Tentar de novo/ }));
    expect(FakeWebSocket.instances).toHaveLength(1);
    expect(socket.commands.filter((c) => c.action === 'start')).toHaveLength(2);
  });

  it('tells the user when the connection drops mid-run', async () => {
    const user = userEvent.setup();
    await boot();
    await user.click(screen.getByRole('radio', { name: /EPG population/ }));
    await user.click(screen.getByRole('button', { name: /Injetar estímulo e simular/ }));

    const socket = await streamARun();
    await act(async () => socket.drop());

    const alert = await screen.findByRole('alert');
    expect(alert).toHaveTextContent(/conexão/i);
    // Frames already received remain scrubbable.
    expect(screen.getByLabelText('Passo da simulação')).toBeEnabled();
  });

  it('surfaces a WebSocket that never connects', async () => {
    const user = userEvent.setup();
    await boot();
    await user.click(screen.getByRole('radio', { name: /EPG population/ }));
    await user.click(screen.getByRole('button', { name: /Injetar estímulo e simular/ }));

    await act(async () => FakeWebSocket.latest().fail());

    const alert = await screen.findByRole('alert');
    expect(alert).toHaveTextContent(/Sem conexão com o servidor/i);
    expect(alert).toHaveTextContent(/flywire_api\.run/);
  });

  it('warns about an unrecognised server message without breaking the run', async () => {
    const user = userEvent.setup();
    await boot();
    await user.click(screen.getByRole('radio', { name: /EPG population/ }));
    await user.click(screen.getByRole('button', { name: /Injetar estímulo e simular/ }));

    const socket = FakeWebSocket.latest();
    await act(async () => {
      socket.open();
      socket.emitRaw('<html>proxy error</html>');
    });

    const notice = await screen.findByText(/Mensagem inesperada do servidor/);
    expect(notice.closest('.banner')).toHaveClass('banner--warning');
    expect(screen.getByText(/não é JSON válido/)).toBeInTheDocument();
  });

  it('shows a recoverable error when the circuit itself fails to load', async () => {
    vi.unstubAllGlobals();
    const failing = mockApi({ graph: new Error('connect ECONNREFUSED 127.0.0.1:8000') });
    mockWebSocket();

    render(<App />);
    const alert = await screen.findByRole('alert');
    expect(alert).toHaveTextContent(/Não foi possível carregar o circuito/i);

    // Retrying re-issues the requests instead of forcing a page reload.
    const callsBefore = failing.mock.calls.length;
    await userEvent.setup().click(
      within(alert).getByRole('button', { name: /Tentar de novo/ }),
    );
    await waitFor(() => expect(failing.mock.calls.length).toBeGreaterThan(callsBefore));
  });

  it('still renders when the optional provenance and defaults calls fail', async () => {
    vi.unstubAllGlobals();
    mockApi({ provenance: new Error('boom'), defaults: new Error('boom') });
    mockWebSocket();

    render(<App />);
    await waitFor(() => expect(screen.getByTestId('force-graph')).toBeInTheDocument());
    // The required honesty text comes from /api/circuit, so it is still there.
    expect(screen.getByText(SUMMARY.disclaimer)).toBeVisible();
    // …but the snapshot version, which only provenance knows, is not invented.
    expect(screen.queryByText(/v783\.0/)).not.toBeInTheDocument();
  });
});

describe('selecting a stimulus source by clicking the graph', () => {
  beforeEach(() => {
    mockApi();
    mockWebSocket();
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it('opens the inspector with the data the API returned, and nothing more', async () => {
    const user = userEvent.setup();
    await boot();

    // Index 4 is the neuron with no transmitter and no soma position.
    const node = screen
      .getAllByTestId('graph-node')
      .find((element) => element.dataset.rootId === '720575940603823462')!;
    await user.click(node);

    const inspector = screen.getByRole('region', { name: /Inspetor/i });
    expect(within(inspector).getByText('720575940603823462')).toBeInTheDocument();
    expect(within(inspector).getByText('PEN_a(PEN1)')).toBeInTheDocument();
    // Missing fields say so; they are not filled with something plausible.
    expect(within(inspector).getAllByText('não disponível').length).toBeGreaterThanOrEqual(2);
  });

  it('promotes the clicked neuron to the stimulus source and runs with it', async () => {
    const user = userEvent.setup();
    await boot();

    const node = screen
      .getAllByTestId('graph-node')
      .find((element) => element.dataset.rootId === '720575940613829900')!;
    await user.click(node);
    await user.click(screen.getByRole('button', { name: /usar como origem do estímulo/ }));

    // The panel switched to the "chosen neurons" mode and shows the chip.
    expect(screen.getByText(/1 neurônio receberá o estímulo/)).toBeInTheDocument();

    await user.click(screen.getByRole('button', { name: /Injetar estímulo e simular/ }));
    const socket = FakeWebSocket.latest();
    await act(async () => socket.open());

    const start = socket.commands.find((c) => c.action === 'start')!;
    expect((start.request as Record<string, unknown>).source).toEqual({
      root_ids: ['720575940613829900'],
    });
  });

  it('blocks the run while no source is chosen, and says why', async () => {
    const user = userEvent.setup();
    await boot();

    await user.click(screen.getByRole('tab', { name: 'Neurônios escolhidos' }));
    expect(screen.getByRole('button', { name: /Injetar estímulo e simular/ })).toBeDisabled();
    expect(screen.getByText(/Clique em neurônios no grafo/)).toBeInTheDocument();
    expect(FakeWebSocket.instances).toHaveLength(0);
  });

  it('builds a cell-type selection and reports how many neurons it covers', async () => {
    const user = userEvent.setup();
    await boot();

    await user.click(screen.getByRole('tab', { name: 'Por tipo celular' }));
    await user.click(screen.getByRole('checkbox', { name: /Delta7/ }));
    expect(screen.getByTestId('selection-count')).toHaveTextContent('2 neurônios');

    await user.selectOptions(screen.getByLabelText(/Hemisfério/i), 'left');
    expect(screen.getByTestId('selection-count')).toHaveTextContent('1 neurônio');

    await user.click(screen.getByRole('button', { name: /Injetar estímulo e simular/ }));
    const socket = FakeWebSocket.latest();
    await act(async () => socket.open());
    const start = socket.commands.find((c) => c.action === 'start')!;
    expect((start.request as Record<string, unknown>).source).toEqual({
      cell_types: ['Delta7'],
      side: 'left',
    });
  });
});
