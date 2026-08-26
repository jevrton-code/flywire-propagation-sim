import '@testing-library/jest-dom/vitest';
import { afterEach, vi } from 'vitest';
import { cleanup } from '@testing-library/react';

afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
});

// jsdom has no layout engine, so every element measures 0x0 and the graph would
// never mount. Give it a viewport-sized box.
Object.defineProperty(HTMLElement.prototype, 'clientWidth', {
  configurable: true,
  get() {
    return 900;
  },
});
Object.defineProperty(HTMLElement.prototype, 'clientHeight', {
  configurable: true,
  get() {
    return 600;
  },
});

if (typeof globalThis.ResizeObserver === 'undefined') {
  globalThis.ResizeObserver = class {
    observe() {}
    unobserve() {}
    disconnect() {}
  } as unknown as typeof ResizeObserver;
}

// jsdom implements neither of these; the timeline canvas and the smooth scroll
// from the "ver as N simplificações" button both touch them.
HTMLCanvasElement.prototype.getContext = vi.fn(() => null) as never;
Element.prototype.scrollIntoView = vi.fn();

if (typeof globalThis.requestAnimationFrame === 'undefined') {
  globalThis.requestAnimationFrame = ((callback: FrameRequestCallback) =>
    setTimeout(() => callback(performance.now()), 16) as unknown as number) as never;
  globalThis.cancelAnimationFrame = ((handle: number) =>
    clearTimeout(handle)) as never;
}
