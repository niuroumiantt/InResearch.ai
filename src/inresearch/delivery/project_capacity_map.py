#!/usr/bin/env python3
"""按需输出示例：项目库容量最大的 N 个数据中心园区 → 世界地图 PDF。

    python3 manage.py map           # Top 10，生成 HTML + PDF（reports/output/）
    python3 manage.py map 15        # Top 15

零 Python 依赖；PDF 由本机 Chrome 无头渲染（没有 Chrome 时只出 HTML）。
口径纪律：复用行业当前有效投影；组合、重复、非活跃与含区间的记录不参与单园区排名。
可排名容量 = 单值分期合计并按状态着色
（运营 L8+ / 在建 L6-7 / 规划 L1-5）；用电量为满载推算（公式见图注），非实测。
"""

from inresearch.paths import project_root
from inresearch.storage.layout import workspace_path
from inresearch.storage.files import atomic_write
from inresearch.knowledge import industry
import json
import subprocess
import sys
from datetime import date
from pathlib import Path

ROOT = project_root()
OUT = workspace_path("reports/output", ROOT)
CHROME = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"

# 裁剪窗口（经度/纬度）与画布
LON0, LON1, LAT0, LAT1 = -135, 80, 0, 62
W = 1500
H = W * (LAT1 - LAT0) / (LON1 - LON0) * 1.3  # 纬度方向略拉伸补偿高纬变形


def xy(lon, lat):
    x = (lon - LON0) / (LON1 - LON0) * W
    y = (LAT1 - lat) / (LAT1 - LAT0) * H
    return round(x, 1), round(y, 1)


def cap_total(p):
    """Current rankable IT MW, or None when no full single-value ranking exists."""
    view = industry.project(p)
    return None if _exclusion(view) else view['total_mw']


def cap_by_bucket(p):
    """可排名记录的 (L8+, L6-7, L1-5)，不可排名返回 None。参数为原记录。"""
    view = industry.project(p)
    return None if _exclusion(view) else tuple(view['capacity'][stage] for stage in industry.STAGES)


def _exclusion(view):
    # Reasons are mutually exclusive for the map's explanatory counts.
    if view['portfolio']: return 'portfolio'
    if view.get('duplicate_of'): return 'duplicate'
    if view['lifecycle'] != 'active': return 'inactive'
    # Mixed exact/range phases cannot be ranked by their exact subtotal either.
    if view['capacity_ranged']: return 'range'
    if not view['capacity_known']: return 'unknown'
    if view['total_mw'] <= 0: return 'nonpositive'
    return None


def ranking(projects, n=10):
    """Project once through the shared capacity contract; never rank partial totals."""
    sites = []
    excluded = dict.fromkeys(('portfolio', 'duplicate', 'inactive', 'range', 'unknown', 'nonpositive'), 0)
    for raw in projects:
        view = industry.project(raw)
        reason = _exclusion(view)
        if reason:
            excluded[reason] += 1
        else:
            sites.append(view)
    sites.sort(key=lambda p: (-p['total_mw'], p['site_id']))
    return {'rows': sites[:n], 'eligible': len(sites), 'excluded': excluded}


def world_paths():
    geo = json.loads((ROOT / "web/assets" / "world.geo.json").read_text(encoding="utf-8"))
    paths = []
    for f in geo["features"]:
        g = f["geometry"]
        polys = g["coordinates"] if g["type"] == "MultiPolygon" else [g["coordinates"]]
        d = []
        for poly in polys:
            for ring in poly:
                pts = [xy(lon, lat) for lon, lat in ring[::2]]  # 隔点采样减小体积
                if len(pts) < 3:
                    continue
                d.append("M" + " L".join(f"{x} {y}" for x, y in pts) + " Z")
        if d:
            paths.append("".join(d))
    return paths


def main():
    n = int(sys.argv[1]) if len(sys.argv) > 1 and sys.argv[1].isdigit() else 10
    today = date.today().isoformat()
    projects = json.loads(workspace_path("data/projects.json", ROOT).read_text(encoding="utf-8"))["records"]
    ranked = ranking(projects, n)
    top, excluded = ranked['rows'], ranked['excluded']

    COLORS = {"op": "#16a34a", "bu": "#d97706", "pl": "#9ca3af"}
    dots, rows = [], []
    for i, p in enumerate(top, 1):
        total = p['total_mw']
        op, bu, pl = (p['capacity'][stage] for stage in industry.STAGES)
        color = COLORS["op"] if op >= max(bu, pl) else (COLORS["bu"] if bu >= pl else COLORS["pl"])
        twh = total * 1.2 * 0.9 * 8760 / 1e6
        rows.append((i, p, total, op, bu, pl, twh, color))
        if p.get("coordinates"):
            lat, lon = p["coordinates"]
            x, y = xy(lon, lat)
            r = max(7, min(20, (total / 5000) ** 0.5 * 20))
            dots.append(f'<circle cx="{x}" cy="{y}" r="{r}" fill="{color}" fill-opacity=".75" stroke="#fff" stroke-width="1.5"/>'
                        f'<text x="{x}" y="{y + 4}" text-anchor="middle" font-size="11" font-weight="700" fill="#fff">{i}</text>')

    land = "".join(f'<path d="{d}" fill="#dde3ea" stroke="#b8c2cd" stroke-width="0.4"/>' for d in world_paths())
    table = "".join(
        f'<tr><td><span class="rk" style="background:{c}">{i}</span></td>'
        f'<td>{p["name"]}<div class="loc">{p["location"]} · {p["status"]}</div></td>'
        f'<td class="num">{total:,.0f}</td>'
        f'<td class="num">{op:,.0f} / {bu:,.0f} / {pl:,.0f}</td>'
        f'<td class="num">{twh:.1f}</td></tr>'
        for i, p, total, op, bu, pl, twh, c in rows)

    html = f"""<!DOCTYPE html><html lang="zh-CN"><head><meta charset="UTF-8"><title>全球最大数据中心园区 Top {n}</title>
<style>
  @page {{ size: A4 landscape; margin: 8mm; }}
  * {{ margin:0; padding:0; box-sizing:border-box; }}
  body {{ font: 12px/1.5 -apple-system, "PingFang SC", sans-serif; color:#1a1d24; padding: 10px 14px; }}
  h1 {{ font-size:19px; margin-bottom:2px; }}
  .sub {{ color:#6b7280; font-size:11px; margin-bottom:8px; }}
  svg {{ width:100%; border:1px solid #e5e7eb; border-radius:6px; background:#f3f6f9; }}
  table {{ width:100%; border-collapse:collapse; margin-top:8px; font-size:10.5px; }}
  th,td {{ padding:3px 8px; border-bottom:1px solid #e5e7eb; text-align:left; vertical-align:top; }}
  th {{ color:#6b7280; font-weight:500; }}
  td.num, th.num {{ text-align:right; font-variant-numeric:tabular-nums; }}
  .rk {{ display:inline-block; width:17px; height:17px; border-radius:50%; color:#fff; text-align:center; line-height:17px; font-weight:700; font-size:10px; }}
  .loc {{ color:#9ca3af; font-size:9.5px; }}
  .note {{ color:#6b7280; font-size:9.5px; margin-top:6px; line-height:1.6; }}
  .legend {{ font-size:10px; color:#6b7280; margin:4px 0; }}
  .legend i {{ display:inline-block; width:10px; height:10px; border-radius:50%; vertical-align:-1px; margin:0 3px 0 10px; }}
</style></head><body>
<h1>全球最大数据中心园区 Top {n} — 布局与用电量</h1>
<div class="sub">inresearch.ai 按需输出 ｜ 数据快照 {today} ｜ 范围：项目库当前活跃、非重复、单值容量园区 ｜ 容量口径：IT 负载 MW（各状态合计，含已标记估算）</div>
<svg viewBox="0 0 {W} {H:.0f}" xmlns="http://www.w3.org/2000/svg">{land}{"".join(dots)}</svg>
<div class="legend">主导状态：<i style="background:{COLORS['op']}"></i>运营 (L8+)<i style="background:{COLORS['bu']}"></i>在建 (L6–7)<i style="background:{COLORS['pl']}"></i>规划 (L1–5)　·　圆面积 ∝ 容量</div>
<table><tr><th></th><th>园区</th><th class="num">合计容量 (MW)</th><th class="num">运营 / 在建 / 规划 (MW)</th><th class="num">满载年耗电估算 (TWh)</th></tr>{table}</table>
<div class="note">⚖ 口径提醒：容量为各状态合计——多数园区大部分容量仍在建/规划中，<b>不得解读为已投运规模</b>；
用电量为满载推算：IT 容量 × PUE 1.2 × 利用率 90% × 8760h（S5 级推算，非实测/非公司披露）；
排名基于本项目库（{ranked['eligible']} 个可排名园区，核验日期见各记录），不代表全球普查。
排除：组合 {excluded['portfolio']}、重复 {excluded['duplicate']}、非活跃 {excluded['inactive']}、含区间 {excluded['range']}、未知 {excluded['unknown']}、非正容量 {excluded['nonpositive']}；
含区间园区的单值部分也不冒充完整容量参与排名；未知容量不等于零。
生成：src/inresearch/delivery/project_capacity_map.py ｜ 数据：data/projects.json ｜ © inresearch.ai</div>
</body></html>"""

    OUT.mkdir(parents=True, exist_ok=True)
    html_path = OUT / f"{today}_全球Top{n}数据中心地图.html"
    pdf_path = html_path.with_suffix(".pdf")
    atomic_write(html_path, html.encode('utf-8'))
    print(f"→ {html_path}")
    if Path(CHROME).exists():
        r = subprocess.run([CHROME, "--headless", "--disable-gpu", "--no-pdf-header-footer",
                            f"--print-to-pdf={pdf_path}", "--landscape", str(html_path)],
                           capture_output=True, text=True, timeout=60)
        if pdf_path.exists():
            print(f"→ {pdf_path}")
        else:
            print("Chrome 渲染失败:", (r.stderr or "")[-200:])
    else:
        print("未找到 Chrome，仅输出 HTML")
    return 0


if __name__ == "__main__":
    sys.exit(main())
