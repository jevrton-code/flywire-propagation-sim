import { useCallback, useEffect, useState } from 'react';

/**
 * Tracks an element's content box, so the canvas can be sized in CSS pixels.
 *
 * Uses a **callback ref**, not `useRef`. The measured element is mounted
 * conditionally (it does not exist during the loading state), and a `useRef`
 * with an empty-dependency effect would observe `null` on the first render and
 * never look again — leaving the graph permanently 0x0 once the data arrived.
 */
export function useElementSize<T extends HTMLElement>() {
  const [element, setElement] = useState<T | null>(null);
  const [size, setSize] = useState({ width: 0, height: 0 });

  const ref = useCallback((node: T | null) => setElement(node), []);

  useEffect(() => {
    if (!element) {
      setSize({ width: 0, height: 0 });
      return;
    }

    const update = () => {
      setSize((current) => {
        const width = element.clientWidth;
        const height = element.clientHeight;
        return current.width === width && current.height === height
          ? current
          : { width, height };
      });
    };

    update();
    // ResizeObserver is absent in jsdom; the component still renders, it just
    // keeps the initial size, which is all a unit test needs.
    if (typeof ResizeObserver === 'undefined') return;
    const observer = new ResizeObserver(update);
    observer.observe(element);
    return () => observer.disconnect();
  }, [element]);

  return { ref, ...size };
}
