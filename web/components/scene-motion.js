/** One writer for a continuous scene state; superseded frames cannot write. */
export function createSceneMotion({requestFrame = requestAnimationFrame,
  cancelFrame = cancelAnimationFrame, now = () => performance.now(),
  reducedMotion = () => matchMedia('(prefers-reduced-motion: reduce)').matches} = {}) {
  let revision = 0, frame = null;
  function cancel() {
    revision++;
    if (frame !== null) cancelFrame(frame);
    frame = null;
  }
  function run(duration, update) {
    cancel();
    const own = revision, start = now();
    function step(time) {
      if (own !== revision) return;
      frame = null;
      const progress = duration <= 0 || reducedMotion() ? 1 : Math.min(1, Math.max(0, (time - start) / duration));
      update(progress);
      if (own === revision && progress < 1) frame = requestFrame(step);
    }
    step(start);
  }
  return {run, cancel};
}
