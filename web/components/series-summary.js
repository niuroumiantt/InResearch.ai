/* One price-series summary for both 3D dossiers. */
export function latest(prices, sid) {
  const pts = prices.records.filter(r => r.series_id === sid).sort((a, b) => a.as_of < b.as_of ? 1 : -1);
  return pts[0];
}
export const escapeHtml = s => String(s ?? "").replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;").replace(/'/g, "&#39;");
export function sparkline(prices, sid) {
  const pts = prices.records.filter(r => r.series_id === sid && typeof r.value === "number")
    .sort((a, b) => a.as_of < b.as_of ? -1 : 1);
  if (pts.length < 3) return null;
  const W = 292, H = 56, PX = 3, PY = 6;
  const vs = pts.map(r => r.value);
  const lo = Math.min(...vs), hi = Math.max(...vs), span = hi - lo || 1;
  const X = i => PX + i / (pts.length - 1) * (W - 2 * PX);
  const Y = v => H - PY - (v - lo) / span * (H - 2 * PY);
  const line = pts.map((r, i) => `${i ? "L" : "M"}${X(i).toFixed(1)},${Y(r.value).toFixed(1)}`).join("");
  const last = pts[pts.length - 1];
  const hits = pts.map((r, i) =>
    `<circle cx="${X(i).toFixed(1)}" cy="${Y(r.value).toFixed(1)}" r="9" fill="transparent" data-v="${r.value.toLocaleString()} ${escapeHtml(r.unit)}" data-d="${escapeHtml(r.as_of)}"/>`).join("");
  return `<div class="spark-wrap">
    <div class="sname"><span>${escapeHtml(sid)}</span><b>${last.value.toLocaleString()} ${escapeHtml(last.unit)}</b></div>
    <svg class="spark" width="${W}" height="${H}" viewBox="0 0 ${W} ${H}" style="display:block">
      <path d="${line}" fill="none" stroke="var(--accent)" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
      <circle cx="${X(pts.length - 1).toFixed(1)}" cy="${Y(last.value).toFixed(1)}" r="3" fill="var(--accent)"/>
      ${hits}
    </svg>
    <div class="sname"><span style="font-size:10px">${escapeHtml(pts[0].as_of)} → ${escapeHtml(last.as_of)}</span><span style="font-size:10px">区间 ${lo.toLocaleString()}–${hi.toLocaleString()}</span></div>
  </div>`;
}
