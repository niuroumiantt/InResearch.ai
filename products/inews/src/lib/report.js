// 每日 Excel 报表 —— 与网站展示口径严格一致:相关 + 价值≥2 + 合并转载留
// 首发。做成服务器现场生成(/api/report.xlsx)而不是发附件:邮件接口只收
// 内联 base64,几百 KB 的文件经对话上下文搬运会静默损坏(2026-09-02 实测,
// sha256 校验拦下);链接指向的文件永远新鲜,还能随手改时间窗。

import { getDb } from './db.js';
import { buildXlsx } from './xlsx.js';

// 跳转短链要绝对地址。域名不写死在库表层 —— 换域名改环境变量即可。
const PUBLIC_URL = (process.env.ST_PUBLIC_URL || 'https://inews.today').replace(/\/$/, '');

const TIER = { 3: '必读', 2: '可读' };

const fmtShanghai = new Intl.DateTimeFormat('zh-CN', {
  timeZone: 'Asia/Shanghai', year: 'numeric', month: '2-digit', day: '2-digit',
  hour: '2-digit', minute: '2-digit', hour12: false,
});

/**
 * 组装报表行并打包成 xlsx。
 * 排序与每日邮件一致:档位降序 → 转载数降序(重要性的市场投票) → 时间降序。
 * @returns {{rows: string[][], buf: Buffer, count: number}}
 */
export function reportXlsx({ hours = 24, now = Date.now() } = {}) {
  const db = getDb();
  const items = db.prepare(`SELECT id, title, title_zh, domain, publisher, published_at,
        value, COALESCE(cluster_n, 1) AS n
      FROM articles
      WHERE relevant = 1 AND is_original = 1 AND value >= 2 AND published_at > ?
      ORDER BY value DESC, n DESC, published_at DESC`)
    .all(now - hours * 3600_000);
  const rows = [['时间(上海)', '档位', '转载数', '标题', '原文标题', '来源', '网址']];
  for (const it of items) {
    const zh = it.title_zh || it.title;
    rows.push([
      fmtShanghai.format(new Date(it.published_at)),
      TIER[it.value] || String(it.value),
      String(it.n),
      zh,
      zh === it.title ? '' : it.title,
      it.publisher || it.domain,
      `${PUBLIC_URL}/r/${it.id}`,
    ]);
  }
  return { rows, buf: buildXlsx(rows, { sheet: `过去${hours}小时` }), count: items.length };
}
