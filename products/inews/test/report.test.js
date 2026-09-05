// 每日报表:零依赖生成的 .xlsx(本质是装 XML 的 zip)+ 公开下载端点。
// 邮件附件走不通(接口只收内联 base64,大文件经上下文搬运会损坏),
// 所以改成服务器现场生成、邮件里放链接 —— 文件永远是新鲜的。
import { test, after } from 'node:test';
import assert from 'node:assert/strict';
import { rmSync } from 'node:fs';
import { join, dirname } from 'node:path';
import { fileURLToPath } from 'node:url';

const HERE = dirname(fileURLToPath(import.meta.url));
const DB = join(HERE, 'tmp-report.db');
for (const s of ['', '-wal', '-shm']) rmSync(DB + s, { force: true });
process.env.SINGLETITLE_DB = DB;

const { buildXlsx } = await import('../src/lib/xlsx.js');
const { reportXlsx } = await import('../src/lib/report.js');
const { getDb } = await import('../src/lib/db.js');
const { createServer } = await import('../src/server.js');

/** 迷你 zip 读取器:按 EOCD → 中央目录 → 本地条目走一遍,重算每个条目的
 *  CRC-32 与头部比对 —— 差一个字节的 zip 在 Excel 里就是打不开的废文件,
 *  这里必须机器验证,不能靠肉眼看签名。 */
function readZip(buf) {
  const eocdAt = buf.length - 22;
  assert.equal(buf.readUInt32LE(eocdAt), 0x06054b50, 'EOCD 签名');
  const count = buf.readUInt16LE(eocdAt + 10);
  let at = buf.readUInt32LE(eocdAt + 16);
  const entries = [];
  for (let i = 0; i < count; i++) {
    assert.equal(buf.readUInt32LE(at), 0x02014b50, '中央目录签名');
    const crc = buf.readUInt32LE(at + 16);
    const size = buf.readUInt32LE(at + 20);
    const nameLen = buf.readUInt16LE(at + 28);
    const extraLen = buf.readUInt16LE(at + 30);
    const cmtLen = buf.readUInt16LE(at + 32);
    const localAt = buf.readUInt32LE(at + 42);
    const name = buf.toString('utf8', at + 46, at + 46 + nameLen);
    assert.equal(buf.readUInt32LE(localAt), 0x04034b50, `本地头签名: ${name}`);
    const lNameLen = buf.readUInt16LE(localAt + 26);
    const lExtraLen = buf.readUInt16LE(localAt + 28);
    const data = buf.subarray(localAt + 30 + lNameLen + lExtraLen,
      localAt + 30 + lNameLen + lExtraLen + size);
    // 独立重算 CRC(与生成器不同实现路径:逐位查表 vs 这里直接逐位算)。
    let c = 0xffffffff;
    for (const byte of data) {
      c ^= byte;
      for (let k = 0; k < 8; k++) c = c & 1 ? 0xedb88320 ^ (c >>> 1) : c >>> 1;
    }
    assert.equal((c ^ 0xffffffff) >>> 0, crc, `CRC 不符: ${name}`);
    entries.push({ name, data });
    at += 46 + nameLen + extraLen + cmtLen;
  }
  return entries;
}

test('buildXlsx 产出结构完整、CRC 正确的 xlsx,单元格内容正确转义', () => {
  const buf = buildXlsx([
    ['标题', '网址', '时间'],
    ['A&B <公司> 发布 "新品"', 'https://x/1', '2026-09-02 06:30'],
  ]);
  assert.equal(buf.readUInt32LE(0), 0x04034b50, 'zip 签名');
  const entries = readZip(buf);
  const names = entries.map((e) => e.name).sort();
  assert.deepEqual(names, ['[Content_Types].xml', '_rels/.rels', 'xl/_rels/workbook.xml.rels',
    'xl/workbook.xml', 'xl/worksheets/sheet1.xml']);
  const sheet = entries.find((e) => e.name === 'xl/worksheets/sheet1.xml').data.toString();
  assert.ok(sheet.includes('A&amp;B &lt;公司&gt; 发布 &quot;新品&quot;'), 'XML 特殊字符必须转义');
  assert.ok(sheet.includes('https://x/1'));
});

const now = Date.now();
function seed(db, id, { title, zh = null, value = 2, original = 1, n = 1, pub = now - 3600_000 }) {
  db.prepare(`INSERT INTO articles
    (id, url, guid, title, title_zh, domain, published_at, first_seen_at,
     relevance, relevant, dedupe_key, cluster_id, is_original, value, genre, value_src,
     cluster_latest, cluster_n)
    VALUES (?,?,?,?,?, 'example.com', ?, ?, 5, 1, ?, ?, ?, ?, 'other', 'heur', ?, ?)`)
    .run(id, `https://example.com/${id}`, `g${id}`, title, zh, pub, now, `dk${id}`,
      original ? id : id - 1, original, value, original ? pub : null, original ? n : null);
}

test('报表口径与网站一致:价值≥2 的首发,按价值与转载数排序', () => {
  const db = getDb();
  seed(db, 1, { title: 'OpenAI pauses new ChatGPT version', zh: 'OpenAI 暂停新版 ChatGPT', value: 3, n: 7 });
  seed(db, 2, { title: '某公司也用了AI的边角料', value: 1 });          // 档位不够,不进报表
  seed(db, 3, { title: 'Anthropic raises $30B', zh: 'Anthropic 融资 300 亿美元', value: 2, n: 12 });
  seed(db, 4, { title: 'OpenAI pauses new ChatGPT version (转载)', original: 0 });  // 转载不进报表
  seed(db, 5, { title: '窗口外的旧闻', value: 3, pub: now - 48 * 3600_000 });        // 超窗

  const { rows } = reportXlsx({ hours: 24, now });
  const titles = rows.slice(1).map((r) => r[3]);
  assert.deepEqual(titles, ['OpenAI 暂停新版 ChatGPT', 'Anthropic 融资 300 亿美元'],
    '必读在前;边角料、转载、超窗行都不出现');
  assert.ok(rows[0].includes('标题'), '第一行是表头');
  const links = rows.slice(1).map((r) => r[r.length - 1]);
  assert.ok(links.every((l) => /^https:\/\/.+\/r\/\d+$/.test(l)), '网址列用本站跳转短链');
});

const server = createServer();
await new Promise((r) => server.listen(0, r));
const base = `http://127.0.0.1:${server.address().port}`;
after(() => server.close());

test('/api/report.xlsx 公开可下,内容是合法 xlsx 且带展示口径数据', async () => {
  const res = await fetch(base + '/api/report.xlsx?hours=24');
  assert.equal(res.status, 200);
  assert.match(res.headers.get('content-type'), /spreadsheetml/);
  assert.match(res.headers.get('content-disposition'), /attachment.*\.xlsx/);
  const buf = Buffer.from(await res.arrayBuffer());
  const entries = readZip(buf);
  const sheet = entries.find((e) => e.name === 'xl/worksheets/sheet1.xml').data.toString();
  assert.ok(sheet.includes('OpenAI 暂停新版 ChatGPT'), '报表里有必读行');
  assert.ok(!sheet.includes('边角料'), '低档位行不出现');
});
