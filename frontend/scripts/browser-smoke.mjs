/**
 * End-to-end smoke test against the *real* backend and the *real* dev server.
 *
 * Unit tests check that the code does what it says; this checks that the
 * feature works: the graph paints, the WebSocket streams, the animation
 * advances, cancelling works, and a bad request surfaces in the UI instead of
 * only in the console.
 *
 * Usage (both servers must already be running):
 *   python -m flywire_api.run          # http://127.0.0.1:8000
 *   npm run dev                        # http://localhost:5173
 *   npm run smoke -- --headed          # optional
 *
 * Screenshots land in ./smoke-output.
 */

import { chromium } from 'playwright';
import { mkdir } from 'node:fs/promises';
import path from 'node:path';

const BASE = process.env.SMOKE_URL ?? 'http://localhost:5173';
const OUT = path.resolve('smoke-output');
const headed = process.argv.includes('--headed');

const results = [];
function check(name, ok, detail = '') {
  results.push({ name, ok, detail });
  console.log(`${ok ? 'PASS' : 'FAIL'}  ${name}${detail ? ` — ${detail}` : ''}`);
}

async function main() {
  await mkdir(OUT, { recursive: true });
  const browser = await chromium.launch({ headless: !headed });
  const page = await browser.newPage({ viewport: { width: 1680, height: 1050 } });

  const consoleErrors = [];
  page.on('console', (message) => {
    if (message.type() === 'error') consoleErrors.push(message.text());
  });
  page.on('pageerror', (error) => consoleErrors.push(`pageerror: ${error.message}`));

  await page.goto(BASE, { waitUntil: 'networkidle' });

  // --- 1. circuit loads and the honesty surface is present -----------------
  await page.waitForSelector('.viewport canvas', { timeout: 20000 });
  check('grafo renderiza um canvas', true);

  const bar = await page.locator('.provenance-bar__lead').innerText();
  check(
    'aviso "conectoma real / dinâmica de brinquedo" visível sem interação',
    /Conectoma real/i.test(bar) && /153 neurônios/.test(bar),
    bar.slice(0, 90) + '…',
  );

  const simplifications = await page.locator('.notice__card--warn .notice__list li').count();
  check('lista de simplificações renderizada', simplifications >= 10, `${simplifications} itens`);

  const citation = await page
    .locator('.notice__citations li', { hasText: 'Dorkenwald' })
    .count();
  check('citação Dorkenwald et al. (Nature 2024) presente', citation === 1);

  const flywireLink = await page.locator('a[href="https://codex.flywire.ai"]').count();
  check('link para a fonte (codex.flywire.ai) presente', flywireLink >= 1);

  await page.screenshot({ path: path.join(OUT, '01-inicial.png'), fullPage: true });

  // --- 2. run a preset simulation -----------------------------------------
  await page.getByRole('radio').first().check();
  await page.screenshot({ path: path.join(OUT, '02-preset-selecionado.png') });

  const stepText = () => page.locator('.playback__step').innerText();
  await page.getByRole('button', { name: 'Injetar estímulo e simular' }).click();

  await page.waitForFunction(
    () => {
      const el = document.querySelector('.playback__step');
      return el && !/passo 0\b/.test(el.textContent ?? '');
    },
    { timeout: 20000 },
  );
  check('animação avança enquanto os frames chegam', true, await stepText());

  await page.waitForSelector('.firstspike li', { timeout: 25000 });
  const report = await page.locator('.panel', { hasText: 'Resultado da execução' }).innerText();
  check('relatório final renderizado', /circuito recrutado/.test(report));
  await page.screenshot({ path: path.join(OUT, '03-simulacao-completa.png'), fullPage: true });

  // Timeline must have painted something (non-uniform pixels).
  const timelinePainted = await page.evaluate(() => {
    const canvas = document.querySelector('.timeline canvas');
    if (!canvas) return false;
    const ctx = canvas.getContext('2d');
    const data = ctx.getImageData(0, 0, canvas.width, canvas.height).data;
    const seen = new Set();
    for (let i = 0; i < data.length; i += 400) {
      seen.add(`${data[i]},${data[i + 1]},${data[i + 2]}`);
    }
    return seen.size > 5;
  });
  check('timeline por tipo celular pintou dados', timelinePainted);

  // --- 3. playback controls ------------------------------------------------
  await page.getByRole('button', { name: 'Reproduzir do início' }).click();
  await page.waitForTimeout(700);
  const afterReplay = await stepText();
  await page.getByRole('button', { name: 'Pausar' }).click();
  await page.waitForTimeout(400);
  const paused = await stepText();
  await page.waitForTimeout(600);
  check('pausar congela o passo atual', paused === (await stepText()), paused);
  check('replay reinicia a reprodução', /passo \d/.test(afterReplay), afterReplay);

  // --- 4. layouts ----------------------------------------------------------
  for (const layout of ['Posição do soma', 'Força (conectividade)', 'Anel por tipo celular']) {
    await page.getByRole('tab', { name: layout }).click();
    await page.waitForTimeout(1200);
    await page.screenshot({
      path: path.join(OUT, `04-layout-${layout.split(' ')[0].toLowerCase()}.png`),
    });
  }
  check('três layouts alternam sem erro', true);

  // --- 5. selecting a neuron by clicking the graph -------------------------
  // The nodes live on a canvas, so there is nothing to query: sweep the pointer
  // over the ring until the library's hover tooltip appears, then click there.
  const box = await page.locator('.viewport canvas').boundingBox();
  const cx = box.x + box.width / 2;
  const cy = box.y + box.height / 2;
  let hit = null;
  const tooltipVisible = () =>
    page.evaluate(() => {
      const tip = document.querySelector('.float-tooltip-kap');
      return !!tip && tip.style.display !== 'none' && tip.textContent.length > 0;
    });

  outer: for (const scale of [0.26, 0.28, 0.24, 0.3, 0.22]) {
    const radius = Math.min(box.width, box.height) * scale;
    for (let angle = 0; angle < 360; angle += 4) {
      const radians = (angle * Math.PI) / 180;
      const point = [cx + Math.cos(radians) * radius, cy + Math.sin(radians) * radius];
      await page.mouse.move(point[0], point[1]);
      if (await tooltipVisible()) {
        hit = point;
        break outer;
      }
    }
  }
  let inspected = false;
  if (hit) {
    await page.mouse.click(hit[0], hit[1]);
    inspected = await page
      .locator('.inspector__id')
      .waitFor({ timeout: 5000 })
      .then(() => true)
      .catch(() => false);
  }
  check('passar o mouse sobre um nó mostra o cartão de dados', hit !== null);
  check('clicar em um nó abre o inspetor', inspected);

  if (inspected) {
    const rootId = await page.locator('.inspector__id').innerText();
    check(
      'root_id exibido com 18 dígitos, sem perda de precisão',
      /^\d{18}$/.test(rootId.trim()),
      rootId.trim(),
    );
    await page.getByRole('button', { name: 'usar como origem do estímulo' }).click();
    const chip = await page.locator('.chip .mono').first().innerText();
    check('neurônio clicado vira origem do estímulo', chip.trim() === rootId.trim());
    await page.screenshot({ path: path.join(OUT, '05-inspetor.png'), fullPage: true });

    await page.getByRole('button', { name: 'Injetar estímulo e simular' }).click();
    await page.waitForSelector('.tag--stim', { timeout: 20000 });
    check('simulação a partir de um único neurônio escolhido no grafo', true);
  }

  // --- 6. streaming state and cancel --------------------------------------
  // Throttling the *download* makes the streaming state observable in the UI.
  // It does not slow the server down: the backend computes and writes all 201
  // frames in a couple of hundred milliseconds regardless, so by the time the
  // cancel travels back the run is usually already finished. What is verified
  // here is therefore: the running UI appears, the cancel command really goes
  // on the wire, and whichever side wins the race the UI ends coherent — never
  // stuck, and never a red banner over a successful run.
  const cdp = await page.context().newCDPSession(page);
  await cdp.send('Network.enable');
  const sentFrames = [];
  cdp.on('Network.webSocketFrameSent', (event) =>
    sentFrames.push(event.response.payloadData),
  );
  await cdp.send('Network.emulateNetworkConditions', {
    offline: false,
    latency: 80,
    downloadThroughput: 160 * 1024,
    uploadThroughput: 160 * 1024,
  });

  await page.getByRole('tab', { name: 'Estímulos prontos' }).click();
  await page.getByRole('radio').first().check();
  const stepsSlider = page.locator('input[type=range]').first();
  await stepsSlider.fill('200');
  await page.getByRole('button', { name: 'Injetar estímulo e simular' }).click();

  const cancelButton = page.getByRole('button', { name: 'Interromper simulação' });
  let couldCancel = false;
  try {
    await cancelButton.waitFor({ timeout: 8000 });
    couldCancel = true;
  } catch {
    couldCancel = false;
  }
  check('estado "em execução" oferece o botão de interromper', couldCancel);

  if (couldCancel) {
    // While throttled, playback outruns the stream: the UI must say so.
    const buffering = await page
      .locator('.playback__badge--live')
      .waitFor({ timeout: 8000 })
      .then(() => true)
      .catch(() => false);
    check('aviso de "recebendo passos" durante o streaming', buffering);
    await page.screenshot({ path: path.join(OUT, '07-streaming.png'), fullPage: true });

    await cancelButton.click().catch(() => {});
    check(
      'clicar em interromper envia {"action":"cancel"} no socket',
      sentFrames.some((payload) => payload.includes('"cancel"')),
    );

    await page.waitForSelector('.tag--complete, .tag--cancelled', { timeout: 40000 });
    const status = await page
      .locator('.panel', { hasText: 'Resultado da execução' })
      .innerText();
    check(
      'a execução termina em um estado coerente (concluída ou interrompida)',
      /conclu[íi]da|interrompida/i.test(status),
      /interrompida/i.test(status) ? 'interrompida' : 'concluída antes do cancelamento',
    );
    check(
      'nenhum banner de erro após a corrida entre "interromper" e o fim da execução',
      (await page.locator('.banner--error').count()) === 0,
    );
  }

  await cdp.send('Network.emulateNetworkConditions', {
    offline: false,
    latency: 0,
    downloadThroughput: -1,
    uploadThroughput: -1,
  });

  // --- 7. an empty form must not reach the backend -------------------------
  await page.getByRole('tab', { name: 'Neurônios escolhidos' }).click();
  const chips = await page.locator('.chip button').count();
  for (let i = 0; i < chips; i += 1) await page.locator('.chip button').first().click();
  const runDisabled = await page
    .getByRole('button', { name: 'Injetar estímulo e simular' })
    .isDisabled();
  check('form vazio bloqueia a execução (o backend recusaria)', runDisabled);
  const hint = await page.locator('.hint--warn').first().innerText();
  check('motivo do bloqueio explicado ao usuário', hint.length > 10, hint);

  // --- 8. WebSocket failure surfaces in the UI ----------------------------
  // A fresh page: the app reuses an already-open socket, so the constructor has
  // to be replaced before the first run rather than after one has succeeded.
  const wsPage = await browser.newPage({ viewport: { width: 1680, height: 1050 } });
  await wsPage.addInitScript(() => {
    const Original = window.WebSocket;
    window.WebSocket = class extends Original {
      constructor(_url, protocols) {
        super('ws://127.0.0.1:1/porta-morta', protocols);
      }
    };
  });
  await wsPage.goto(BASE, { waitUntil: 'networkidle' });
  await wsPage.waitForSelector('.viewport canvas', { timeout: 20000 });
  await wsPage.getByRole('radio').first().check();
  await wsPage.getByRole('button', { name: 'Injetar estímulo e simular' }).click();

  const banner = wsPage.locator('.banner--error');
  let bannerVisible = false;
  try {
    await banner.waitFor({ timeout: 15000 });
    bannerVisible = true;
  } catch {
    bannerVisible = false;
  }
  check(
    'falha de WebSocket aparece como banner de erro na interface',
    bannerVisible,
    bannerVisible ? (await banner.innerText()).replace(/\n/g, ' ').slice(0, 120) : 'nenhum banner',
  );
  await wsPage.screenshot({ path: path.join(OUT, '08-erro-websocket.png'), fullPage: true });
  await wsPage.close();

  // --- 9. backend unreachable at load time ---------------------------------
  const deadPage = await browser.newPage({ viewport: { width: 1280, height: 900 } });
  // Matched on the pathname, not a glob: in dev the app's own source lives at
  // /src/api/*, and `**/api/**` would abort the modules instead of the calls.
  await deadPage.route(
    (url) => url.pathname.startsWith('/api/'),
    (route) => route.abort(),
  );
  await deadPage.goto(BASE);
  const loadBanner = deadPage.locator('.banner--error');
  let loadBannerVisible = false;
  try {
    await loadBanner.waitFor({ timeout: 15000 });
    loadBannerVisible = true;
  } catch {
    loadBannerVisible = false;
  }
  check(
    'API indisponível no carregamento mostra erro e instrução de como subir o backend',
    loadBannerVisible &&
      /flywire_api\.run/.test(await deadPage.locator('.boot').innerText()),
  );
  await deadPage.screenshot({ path: path.join(OUT, '09-api-fora.png'), fullPage: true });
  await deadPage.close();

  // --- console hygiene -----------------------------------------------------
  const relevant = consoleErrors.filter(
    (message) => !/WebSocket|ws:\/\/127\.0\.0\.1:1|net::ERR/.test(message),
  );
  check(
    'nenhum erro inesperado no console',
    relevant.length === 0,
    relevant.slice(0, 3).join(' | '),
  );

  await browser.close();

  const failed = results.filter((r) => !r.ok);
  console.log(
    `\n${results.length - failed.length}/${results.length} verificações passaram. ` +
      `Capturas em ${OUT}`,
  );
  if (failed.length) process.exitCode = 1;
}

main().catch((error) => {
  console.error(error);
  process.exitCode = 1;
});
