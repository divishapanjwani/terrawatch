import { useEffect, useState } from "react";

const PREFERS_REDUCED_MOTION =
  typeof window !== "undefined" && window.matchMedia?.("(prefers-reduced-motion: reduce)").matches;

/** Animates from 0 to `target` whenever `target` changes (including on
 * mount). Relies on React's own dependency-array comparison to decide
 * when to re-run -- no extra "already animated" guard, since that kind
 * of ref-based guard gets set during the effect's first synchronous
 * pass and then blocks the second pass under StrictMode's dev-only
 * mount/cleanup/remount cycle, leaving the value stuck at 0. */
export function useCountUp(target: number | null, durationMs = 700): number {
  const [value, setValue] = useState(0);

  useEffect(() => {
    if (target == null || !Number.isFinite(target)) return;

    if (PREFERS_REDUCED_MOTION) {
      setValue(target);
      return;
    }

    const start = performance.now();
    let frame: number;

    function tick(now: number) {
      const t = Math.min(1, (now - start) / durationMs);
      const eased = 1 - Math.pow(1 - t, 3); // ease-out cubic
      setValue(target! * eased);
      if (t < 1) frame = requestAnimationFrame(tick);
    }
    frame = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(frame);
  }, [target, durationMs]);

  return target == null ? 0 : value;
}
