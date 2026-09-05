/**
 * Read a canonical environment variable with one temporary legacy alias.
 *
 * During a rename both names may be present so an older image can still be
 * rolled back. They must describe one value: silently preferring either name
 * would let two deployments open different databases or apply different
 * security policy while appearing to share one configuration.
 */
export function envValue(canonical, { legacy, fallback, source = process.env } = {}) {
  const current = source[canonical];
  const previous = legacy ? source[legacy] : undefined;
  const hasCurrent = current !== undefined && current !== '';
  const hasPrevious = previous !== undefined && previous !== '';

  if (hasCurrent && hasPrevious && current !== previous) {
    throw new Error(`环境变量冲突：${canonical} 与旧变量 ${legacy} 必须设置为同一个值`);
  }
  if (hasCurrent) return current;
  if (hasPrevious) return previous;
  return fallback;
}

export function envNumber(canonical, options) {
  const value = envValue(canonical, options);
  const number = Number(value);
  if (!Number.isFinite(number)) {
    throw new Error(`环境变量 ${canonical} 必须是有效数字`);
  }
  return number;
}

export function envFlag(canonical, options) {
  return envValue(canonical, { ...options, fallback: '0' }) === '1';
}
