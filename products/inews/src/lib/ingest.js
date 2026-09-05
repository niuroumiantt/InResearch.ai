import { getDb } from './db.js';
import { parseFeed } from './rss.js';
import { scoreRelevance } from './relevance.js';
import { scoreValue } from './value.js';
import { titleTokens, recentHeads, findSimilarHead } from './cluster.js';
import { regionOf } from './region.js';
import { dedupeKey, parseDate, registrableDomain, stripPublisherSuffix, unwrapGoogleLink } from './normalize.js';
import { admitTechmemeItem } from './techmeme.js';

// Two headlines within this window sharing a dedupe key are the same story.
const CLUSTER_WINDOW_MS = 36 * 60 * 60 * 1000;

/**
 * Parse one feed body and persist its items.
 * @returns {{items:number, fresh:number, kept:number}}
 */
export function ingestFeed(xml, shard, now = Date.now()) {
  return ingestItems(parseFeed(xml).items, shard, now);
}

/**
 * Persist already-parsed items — the shared back half of every channel:
 * GN RSS 和直连 feed 走 ingestFeed(XML),页面监控(watch)自己造 items 直接进来。
 * @returns {{items:number, fresh:number, kept:number}}
 */
export function ingestItems(items, shard, now = Date.now()) {
  const db = getDb();
  // Reserve the WAL writer before any GUID/cluster reads. A deferred
  // SAVEPOINT establishes a read snapshot and can later fail its first write
  // with SQLITE_BUSY_SNAPSHOT when another collector commits in between.
  // One batch-level reservation also prevents a failed concurrent poll from
  // leaving an arbitrary committed prefix of its feed behind.
  return withImmediateTransaction(db, () => ingestItemsLocked(db, items, shard, now));
}

function ingestItemsLocked(db, items, shard, now) {
  let fresh = 0, kept = 0;

  const articleColumns = `id, guid, url, title, domain, publisher, published_at, first_seen_at,
    lang, locale, shard, query, angle, relevance, relevant, hits, dedupe_key, cluster_id,
    is_original, cluster_latest, cluster_n, value, genre, value_src, region`;
  const selGuid = db.prepare(`SELECT ${articleColumns} FROM articles WHERE guid = ?`);
  // Never short-circuit URL lookup because the GUID matched. Old Techmeme rows
  // and independently discovered publisher rows can coexist in upgraded DBs;
  // seeing both is what lets the publisher row win without cloning its URL.
  const selUrlRows = db.prepare(`SELECT ${articleColumns} FROM articles
    WHERE url = ? ORDER BY id`);
  const selReference = db.prepare(
    'SELECT * FROM editorial_references WHERE source = ? AND source_key = ?',
  );
  const selObservation = db.prepare(`SELECT * FROM editorial_observations
    WHERE source=? AND source_key=?`);
  // 相似度聚类的头索引:精确键没中时,再按标题特征找同题故事(措辞不同的
  // 同事件报道)。惰性加载 —— 本批全是重复条目时一次查询都不花。
  let heads = null;
  const allocateArticleId = db.prepare(`UPDATE id_sequences SET next_id=next_id+1
    WHERE name='articles' RETURNING next_id-1 AS id`);
  const ins = db.prepare(`INSERT INTO articles
    (id, url, guid, title, domain, publisher, published_at, first_seen_at, lang, locale,
     angle, shard, query, relevance, relevant, hits, dedupe_key, cluster_id, is_original,
     value, genre, value_src, region)
    VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)`);
  const upsertReference = db.prepare(`INSERT INTO editorial_references
    (source, source_key, article_id, title, url, domain, publisher, selected_at, first_seen_at,
     value, genre, angle, policy, observed_at, observer, observer_rank)
    VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
    ON CONFLICT(source, source_key) DO UPDATE SET
      article_id=excluded.article_id, title=excluded.title, url=excluded.url,
      domain=excluded.domain, publisher=excluded.publisher,
      selected_at=MAX(editorial_references.selected_at, excluded.selected_at),
      first_seen_at=MIN(editorial_references.first_seen_at, excluded.first_seen_at),
      value=excluded.value, genre=excluded.genre, angle=excluded.angle, policy=excluded.policy,
      observed_at=excluded.observed_at, observer=excluded.observer,
      observer_rank=excluded.observer_rank
    WHERE excluded.observed_at > COALESCE(editorial_references.observed_at,
                                           editorial_references.first_seen_at)
       OR (excluded.observed_at = COALESCE(editorial_references.observed_at,
                                            editorial_references.first_seen_at)
           AND excluded.observer_rank > COALESCE(editorial_references.observer_rank, 0))
       OR (excluded.observed_at = COALESCE(editorial_references.observed_at,
                                            editorial_references.first_seen_at)
           AND excluded.observer_rank = COALESCE(editorial_references.observer_rank, 0)
           AND (excluded.url || char(0) || excluded.title)
             > (editorial_references.url || char(0) || editorial_references.title))`);
  const upsertObservation = db.prepare(`INSERT INTO editorial_observations
      (source, source_key, selected_at, observed_at, observer, observer_rank,
       url, title, accepted, reason)
    VALUES (?,?,?,?,?,?,?,?,?,?)
    ON CONFLICT(source, source_key) DO UPDATE SET
      selected_at=MAX(editorial_observations.selected_at, excluded.selected_at),
      observed_at=excluded.observed_at,
      observer=excluded.observer, observer_rank=excluded.observer_rank,
      url=excluded.url, title=excluded.title,
      accepted=excluded.accepted, reason=excluded.reason
    WHERE excluded.observed_at > editorial_observations.observed_at
       OR (excluded.observed_at = editorial_observations.observed_at
           AND excluded.observer_rank > editorial_observations.observer_rank)
       OR (excluded.observed_at = editorial_observations.observed_at
           AND excluded.observer_rank = editorial_observations.observer_rank
           AND (excluded.url || char(0) || excluded.title)
             > (editorial_observations.url || char(0) || editorial_observations.title))`);
  const updateOwnedMetadata = db.prepare(`UPDATE articles SET
    title_zh=CASE WHEN title=? THEN title_zh ELSE NULL END,
    title_zh_at=CASE WHEN title=? THEN title_zh_at ELSE NULL END,
    url=?, title=?, domain=?, publisher=?, lang=?, locale=?, shard=?, query=?,
    dedupe_key=?, region=? WHERE id=?`);

  for (const it of items) {
    const guid = it.guid || it.link;
    if (!guid) continue;

    // 直连 feed 常带整年的历史存档(OpenAI 官方 feed 有上千条老文章)。
    // 这里只收近 14 天的 —— 时间线是新闻流,不是档案馆;GN shard 有
    // when:1h 天然新,不受此限。
    if (shard.feedUrl) {
      const published = parseDate(it.pubDate);
      if (!published || published < now - 14 * 864e5) continue;
    }

    const title = stripPublisherSuffix(it.title, it.sourceName);
    const url = unwrapGoogleLink(it.link);
    const domain = registrableDomain(it.sourceUrl) || registrableDomain(url) || 'unknown';
    const byGuid = selGuid.get(guid);
    // Normal feeds retain GUID identity. Editorial sources deliberately keep
    // going: a later selection may need to attach to an exact publisher URL.
    if (byGuid && !shard.editorialSource) continue;
    if (!shard.editorialSource) fresh++;
    // Google/Feed 的描述只负责“发现”，不能替标题作准入裁决。用户看到并判断的
    // 是标题；描述里顺带出现 AI 正是无关快讯批量混入的根因。
    let { score, relevant, hits } = scoreRelevance({ title, query: shard.q });
    // 直连一手源(官方博客/监管机构)的标题常不带 AI 词 ——「Introducing GPT-6」。
    // 来源本身就是实体,补上这份先验,别让词法闸门错杀官方发布。
    if (shard.feedBoost) {
      score += shard.feedBoost;
      relevant = score >= 3;
      hits = [...hits, 'feed'];
    }

    const published = parseDate(it.pubDate) ?? now;
    let angle = it.angle || shard.angle;
    let worth;
    let editorialVerdict = null;

    if (shard.editorialPolicy === 'techmeme-ai') {
      const verdict = admitTechmemeItem({ ...it, title, link: url, angle: it.angle });
      editorialVerdict = verdict;
      const sourceKey = it.editorialKey || guid;
      if (!verdict.accepted) {
        const changed = withSavepoint(db, () => {
          const prior = selReference.get(shard.editorialSource, sourceKey);
          const observerRank = editorialObserverRank(shard);
          const observation = selObservation.get(shard.editorialSource, sourceKey);
          if (compareEditorialObservation(
            { selected_at: published, observed_at: now, observer_rank: observerRank, url, title },
            observation,
          ) < 0) {
            if (prior?.article_id) {
              const affected = ensureEditorialFloor(db, prior.article_id, {
                relevance: 3, value: prior.value ?? 2, genre: prior.genre,
                angle: prior.angle, hits: [], source: shard.editorialSource,
              });
              refreshDomains(db, affected);
            }
            return false;
          }
          upsertObservation.run(
            shard.editorialSource, sourceKey, published, now, shard.id || '', observerRank,
            url, title, 0, verdict.reason || 'rejected',
          );
          // An accepted selection is a historical fact. A later River edit
          // that fails today's policy cannot revoke it or demote its story.
          if (prior) {
            if (prior.article_id) {
              const affected = ensureEditorialFloor(db, prior.article_id, {
                relevance: 3, value: prior.value ?? 2, genre: prior.genre,
                angle: prior.angle, hits: [], source: shard.editorialSource,
              });
              refreshDomains(db, affected);
            }
            return false;
          }

          const current = selGuid.get(guid);
          if (!current || !ownsTechmemeArticle(current)) return false;
          const exact = preferredUrlRow(selUrlRows.all(url), current.id);
          const affected = new Set();
          // Exact URL proves that the independently found publisher row is the
          // same article. Remove only the generated Techmeme duplicate.
          if (exact && current.url === url) {
            addAll(affected, removeTechmemeArticle(db, current.id, exact.id));
            addAll(affected, repairArticleCluster(db, exact.id).domains);
          } else {
            // Keep the redirect identity stable, but detach a rejected owned
            // row so a hidden former head cannot swallow valid members.
            const otherRef = db.prepare(`SELECT value, genre, angle FROM editorial_references
              WHERE article_id=? LIMIT 1`).get(current.id);
            if (otherRef) {
              addAll(affected, ensureEditorialFloor(db, current.id, {
                relevance: 3, value: otherRef.value ?? 2, genre: otherRef.genre,
                angle: otherRef.angle, hits: [], source: shard.editorialSource,
              }));
            } else {
              addAll(affected, evictOwnedArticle(db, current.id, verdict, hits));
            }
          }
          refreshDomains(db, affected);
          return true;
        });
        if (changed) {
          kept++;
        }
        // The convergence pass may have repaired a legacy pointer chain even
        // when no content fields changed.
        heads = null;
        continue;
      }
      score = verdict.relevance;
      relevant = true;
      hits = verdict.hits;
      angle = verdict.angle;
      worth = { value: verdict.value, genre: verdict.genre };
    } else {
      if (score <= 0) continue;
      worth = scoreValue({ title, angle, relevance: score, relevant: relevant ? 1 : 0 });
    }

    if (shard.editorialSource) {
      const result = withSavepoint(db, () => {
        const affected = new Set();
        let topologyChanged = false;
        let created = false;
        const sourceKey = it.editorialKey || guid;
        const priorReference = selReference.get(shard.editorialSource, sourceKey);
        const observerRank = editorialObserverRank(shard);
        const observation = selObservation.get(shard.editorialSource, sourceKey);
        const staleObservation = compareEditorialObservation(
          { selected_at: published, observed_at: now, observer_rank: observerRank, url, title },
          observation,
        ) < 0;

        // RSS and River can arrive out of order. Once a newer observation has
        // advanced a permanent Techmeme id, an older response must not move its
        // reference or redirect identity backwards. It may still repair the
        // already-selected cluster as a harmless convergence pass.
        if (staleObservation) {
          if (priorReference?.article_id) {
            const staleAffected = ensureEditorialFloor(db, priorReference.article_id, {
              relevance: 3, value: priorReference.value ?? 2, genre: priorReference.genre,
              angle: priorReference.angle, hits: [], source: shard.editorialSource,
            });
            refreshDomains(db, staleAffected);
          }
          return { created: false, topologyChanged: false, newReference: false, stale: true };
        }
        upsertObservation.run(
          shard.editorialSource, sourceKey, published, now, shard.id || '', observerRank,
          url, title, 1, editorialVerdict?.reason || 'accepted',
        );
        const canonicalGuidRow = selGuid.get(guid);
        let guidRow = canonicalGuidRow;
        // A pathological publisher row can already own the Techmeme permalink
        // GUID. Our generated row then uses a deterministic suffix; on later
        // edits the durable reference, not canonical GUID lookup, finds it.
        if ((!guidRow || !ownsTechmemeArticle(guidRow)) && priorReference?.article_id) {
          const referenced = db.prepare(`SELECT ${articleColumns} FROM articles WHERE id=?`)
            .get(priorReference.article_id);
          if (ownsTechmemeArticle(referenced)) guidRow = referenced;
        }
        const urlRows = selUrlRows.all(url);
        let target = preferredUrlRow(urlRows);

        // When an exact publisher URL already exists, it is the canonical row.
        // If the pml GUID still points at an owned legacy/current row, retire
        // only that generated row and repair the cluster it used to head.
        if (target) {
          if (guidRow && guidRow.id !== target.id && ownsTechmemeArticle(guidRow)) {
            if (guidRow.url === target.url) {
              addAll(affected, removeTechmemeArticle(db, guidRow.id, target.id));
            } else if (hasOtherReferences(db, guidRow.id, shard.editorialSource, sourceKey)) {
              addAll(affected, repairArticleCluster(db, guidRow.id).domains);
              db.prepare('UPDATE articles SET guid=? WHERE id=?')
                .run(retiredGuid(guidRow), guidRow.id);
            } else {
              addAll(affected, removeTechmemeArticle(db, guidRow.id));
            }
            topologyChanged = true;
          }
          // A database may contain more than one pre-migration owned copy of
          // the same downstream URL. Exact identity makes reference rebinding
          // safe; independent publisher rows are never candidates for delete.
          for (const duplicate of selUrlRows.all(url)) {
            if (duplicate.id === target.id || !ownsTechmemeArticle(duplicate)) continue;
            addAll(affected, removeTechmemeArticle(db, duplicate.id, target.id));
            topologyChanged = true;
          }
          target = db.prepare(`SELECT ${articleColumns} FROM articles WHERE id=?`).get(target.id);
        } else if (guidRow && ownsTechmemeArticle(guidRow)) {
          // The pml now resolves to another URL. Article ids back /r/:id and
          // are public-cacheable, so never rewrite that redirect in place.
          const oldId = guidRow.id;
          const preserveOld = hasOtherReferences(
            db, oldId, shard.editorialSource, sourceKey,
          );
          if (preserveOld) {
            addAll(affected, repairArticleCluster(db, oldId).domains);
          } else {
            addAll(affected, detachArticle(db, oldId).domains);
            db.prepare('UPDATE editorial_references SET article_id=NULL WHERE article_id=?').run(oldId);
          }
          db.prepare('UPDATE articles SET guid=? WHERE id=?')
            .run(retiredGuid(guidRow), oldId);
          const nextGuid = canonicalGuidRow && canonicalGuidRow.id !== oldId
            ? `${guid}#editorial:${sourceKey}` : guid;
          const newId = insertArticle(ins, {
            id: Number(allocateArticleId.get().id),
            url, guid: nextGuid, title, domain, publisher: it.sourceName || null, published, now,
            lang: guidRow.lang || shard.locale.lang, locale: guidRow.locale || shard.locale.id,
            angle, shard: guidRow.shard === 'feed:techmeme' ? shard.id : guidRow.shard,
            query: guidRow.shard === 'feed:techmeme' ? shard.q : guidRow.query,
            relevance: score, relevant: true, hits, value: worth.value, genre: worth.genre,
            valueSrc: 'editorial', region: regionOf(domain, shard.locale.id),
          });
          addAll(affected, attachEditorialArticleToExactCluster(
            db, newId, new Set([oldId]),
          ).domains);
          if (!preserveOld) {
            db.prepare('DELETE FROM articles WHERE id=?').run(oldId);
            clearMergeVerdicts(db, oldId);
          }
          affected.add(guidRow.domain);
          target = db.prepare(`SELECT ${articleColumns} FROM articles WHERE id=?`).get(newId);
          topologyChanged = true;
          created = true;
        } else {
          // A non-owned GUID collision is never permission to mutate that row.
          // It is pathological, but a deterministic suffix still preserves the
          // publisher row and lets exact URL lookup converge on the next poll.
          const insertGuid = guidRow ? `${guid}#editorial:${sourceKey}` : guid;
          const newId = insertArticle(ins, {
            id: Number(allocateArticleId.get().id),
            url, guid: insertGuid, title, domain, publisher: it.sourceName || null,
            published, now, lang: shard.locale.lang, locale: shard.locale.id,
            angle, shard: shard.id, query: shard.q, relevance: score, relevant: true,
            hits, value: worth.value, genre: worth.genre, valueSrc: 'editorial',
            region: regionOf(domain, shard.locale.id),
          });
          addAll(affected, attachEditorialArticleToExactCluster(db, newId).domains);
          target = db.prepare(`SELECT ${articleColumns} FROM articles WHERE id=?`).get(newId);
          topologyChanged = true;
          created = true;
        }

        if (!target) throw new Error(`Techmeme target disappeared for ${sourceKey}`);
        if (ownsTechmemeArticle(target)) {
          const nextDk = dedupeKey(title);
          const recluster = target.title !== title || target.dedupe_key !== nextDk;
          if (recluster) {
            addAll(affected, detachArticle(db, target.id).domains);
            clearMergeVerdicts(db, target.id);
            topologyChanged = true;
          }
          const targetShard = target.shard === 'feed:techmeme' ? shard.id : (target.shard || shard.id);
          const targetQuery = target.shard === 'feed:techmeme' ? shard.q : (target.query || shard.q);
          updateOwnedMetadata.run(
            title, title, url, title, domain, it.sourceName || null,
            target.lang || shard.locale.lang, target.locale || shard.locale.id,
            targetShard, targetQuery, nextDk, regionOf(domain, shard.locale.id), target.id,
          );
          affected.add(target.domain);
          affected.add(domain);
          if (recluster) {
            addAll(affected, attachEditorialArticleToExactCluster(db, target.id).domains);
          }
        }

        // source_key, not GUID, is the durable state-machine identity. A row
        // retained for another pml has a tombstoned GUID; when this pml later
        // moves too, priorReference is the only way to find and retire the now
        // unreferenced generated article.
        if (priorReference?.article_id && priorReference.article_id !== target.id) {
          const priorArticle = db.prepare('SELECT * FROM articles WHERE id=?')
            .get(priorReference.article_id);
          if (priorArticle && ownsTechmemeArticle(priorArticle)
              && !hasOtherReferences(db, priorArticle.id, shard.editorialSource, sourceKey)) {
            addAll(affected, removeTechmemeArticle(db, priorArticle.id));
            topologyChanged = true;
          } else if (priorArticle) {
            // The source_key is about to move. Rebuild the old component while
            // ignoring that soon-to-be-replaced pointer, restoring publisher
            // scoring unless another active selection still supports a floor.
            addAll(affected, reconcileEditorialComponent(db, priorArticle.id, {
              excludeSource: shard.editorialSource, excludeKey: sourceKey,
            }).domains);
          }
        }

        // Repair first, then make both the selected row and its display head
        // satisfy the durable editorial floor. A low-score exact publisher row
        // is therefore visible in the merged timeline immediately.
        addAll(affected, ensureEditorialFloor(db, target.id, {
          relevance: score, value: worth.value, genre: worth.genre,
          angle, hits, source: shard.editorialSource,
        }, priorReference ? {
          excludeSource: shard.editorialSource, excludeKey: sourceKey,
        } : undefined));
        refreshDomains(db, affected);

        // Provenance is the final write: any observer that sees the reference
        // necessarily sees a valid cluster and initialized domain statistics.
        upsertReference.run(
          shard.editorialSource, sourceKey, target.id, title, url, domain,
          it.sourceName || null, published, now, worth.value, worth.genre, angle,
          editorialVerdict?.policy || shard.editorialPolicy || null,
          now, shard.id || '', observerRank,
        );
        return { created, topologyChanged, newReference: !priorReference };
      });
      if (result.created) fresh++;
      if (result.created || result.topologyChanged || result.newReference) kept++;
      heads = null;
      continue;
    }

    // A topology rebuild now includes reversible editorial overlays, so the
    // normal publisher path needs the same atomic item boundary as editorial
    // ingest. Readers can never observe a half-rebuilt cluster/base/floor.
    withSavepoint(db, () => {
      const dk = dedupeKey(title);
      // 两级归并:①精确键(逐字转载);②标题特征相似(同事件不同措辞)。
      const tokens = titleTokens(title);
      let head = exactClusterHead(db, dk, published);
      if (!head) {
        if (heads === null) heads = recentHeads(db, CLUSTER_WINDOW_MS, now);
        head = findSimilarHead(heads, tokens);
      }

      const articleId = Number(allocateArticleId.get().id);
      const info = ins.run(
        articleId, url, guid, title, domain, it.sourceName || null, published, now,
        shard.locale.lang, shard.locale.id, angle, shard.id, shard.q,
        score, relevant ? 1 : 0, hits.join(','), dk,
        head ? head.id : null, head ? 0 : 1,
        worth.value, worth.genre, 'heur', regionOf(domain, shard.locale.id),
      );
      if (!head) {
        // First of its cluster: point at itself so grouping is uniform.
        // 聚类元数据(最新动态/成员数)物化在头行,时间线查询零子查询。
        db.prepare('UPDATE articles SET cluster_id = id, cluster_latest = ?, cluster_n = 1 WHERE id = ?')
          .run(published, info.lastInsertRowid);
        // 新头进内存索引,同一批里的后续同题条目能立刻聚上来。
        if (heads !== null) heads.unshift({
          id: Number(info.lastInsertRowid), published_at: published, tokens,
        });
      } else {
        if (published < head.published_at) {
          const repaired = repairArticleCluster(db, Number(info.lastInsertRowid));
          refreshDomains(db, repaired.domains);
          heads = null;
        } else {
          db.prepare(`UPDATE articles SET cluster_latest = MAX(COALESCE(cluster_latest, published_at), ?),
                                          cluster_n = COALESCE(cluster_n, 1) + 1 WHERE id = ?`)
            .run(published, head.id);
        }
      }
      if (!(head && published < head.published_at)) {
        touchDomain(db, domain, now, relevant, !head, head ? published - head.published_at : 0);
      }
    });
    kept++;
  }
  return { items: items.length, fresh, kept };
}

function withImmediateTransaction(db, fn) {
  // No production caller currently wraps ingest, but keep composition safe for
  // maintenance scripts that deliberately own a wider transaction.
  if (db.isTransaction) return fn();
  db.exec('BEGIN IMMEDIATE');
  try {
    const value = fn();
    db.exec('COMMIT');
    return value;
  } catch (error) {
    try { db.exec('ROLLBACK'); } catch { /* preserve the ingest error */ }
    throw error;
  }
}

function withSavepoint(db, fn) {
  db.exec('SAVEPOINT inews_editorial_item');
  try {
    const value = fn();
    db.exec('RELEASE SAVEPOINT inews_editorial_item');
    return value;
  } catch (error) {
    db.exec('ROLLBACK TO SAVEPOINT inews_editorial_item');
    db.exec('RELEASE SAVEPOINT inews_editorial_item');
    throw error;
  }
}

function insertArticle(statement, row) {
  const info = statement.run(
    row.id, row.url, row.guid, row.title, row.domain, row.publisher, row.published, row.now,
    row.lang, row.locale, row.angle, row.shard, row.query,
    row.relevance, row.relevant ? 1 : 0, (row.hits || []).join(','), dedupeKey(row.title),
    null, 0, row.value, row.genre, row.valueSrc, row.region,
  );
  return Number(info.lastInsertRowid);
}

function preferredUrlRow(rows, excludeId = null) {
  const candidates = rows.filter((row) => row.id !== excludeId);
  return candidates.find((row) => !ownsTechmemeArticle(row)) || candidates[0] || null;
}

function addAll(target, values) {
  for (const value of values || []) if (value) target.add(value);
}

/** Read the whole connected component, including legacy pointer chains. */
function clusterComponent(db, articleId) {
  const get = db.prepare(`SELECT id, cluster_id, published_at, domain
    FROM articles WHERE id=?`);
  const children = db.prepare(`SELECT id, cluster_id, published_at, domain
    FROM articles WHERE cluster_id=?`);
  const queue = [Number(articleId)];
  const queued = new Set(queue);
  const rows = new Map();
  while (queue.length) {
    const id = queue.shift();
    const row = get.get(id);
    if (row) {
      rows.set(row.id, row);
      if (row.cluster_id != null && !queued.has(row.cluster_id)) {
        queued.add(row.cluster_id);
        queue.push(row.cluster_id);
      }
    }
    for (const child of children.all(id)) {
      rows.set(child.id, child);
      if (!queued.has(child.id)) {
        queued.add(child.id);
        queue.push(child.id);
      }
    }
  }
  return [...rows.values()];
}

/** Restore one-hop roots and all materialized head fields for a component. */
function rebuildRows(db, rows, editorialOptions = {}) {
  const live = rows.filter((row, i, all) => row
    && all.findIndex((other) => other.id === row.id) === i
    && db.prepare('SELECT 1 ok FROM articles WHERE id=?').get(row.id));
  const domains = new Set(live.map((row) => row.domain));
  if (!live.length) return { head: null, domains };
  live.sort((a, b) => a.published_at - b.published_at || a.id - b.id);
  const head = live[0];
  const clear = db.prepare(`UPDATE articles SET cluster_id=?, is_original=0,
    cluster_latest=NULL, cluster_n=NULL WHERE id=?`);
  for (const row of live) clear.run(head.id, row.id);
  db.prepare(`UPDATE articles SET is_original=1, cluster_latest=?, cluster_n=? WHERE id=?`)
    .run(Math.max(...live.map((row) => row.published_at)), live.length, head.id);
  reconcileEditorialRows(db, live, head.id, domains, editorialOptions);
  return { head, domains };
}

function reconcileEditorialRows(db, members, headId, domains, options = {}) {
  for (const member of members) restoreEditorialBase(db, member.id, domains);
  const references = db.prepare(`SELECT source, source_key, value, genre, angle
    FROM editorial_references WHERE article_id=?`);
  const floors = [];
  for (const member of members) {
    for (const reference of references.all(member.id)) {
      if (reference.source === options.excludeSource
          && reference.source_key === options.excludeKey) continue;
      floors.push({ ...reference, articleId: member.id });
    }
  }
  // Low floors first: the maximum value wins, and equal-value shape ties are
  // deterministic (lexicographically greatest source/key), matching the SQL
  // topology trigger used by merge.js.
  floors.sort((a, b) => Number(a.value ?? 2) - Number(b.value ?? 2)
    || a.source.localeCompare(b.source) || a.source_key.localeCompare(b.source_key));
  for (const reference of floors) {
      applyEditorialFloorRows(db, reference.articleId, headId, {
        relevance: 3, value: reference.value ?? 2, genre: reference.genre,
        angle: reference.angle, hits: [], source: reference.source,
      }, domains);
  }
}

function reconcileEditorialComponent(db, articleId, options = {}) {
  return rebuildRows(db, clusterComponent(db, articleId), options);
}

function repairArticleCluster(db, articleId, editorialOptions = {}) {
  return rebuildRows(db, clusterComponent(db, articleId), editorialOptions);
}

function detachArticle(db, articleId) {
  const component = clusterComponent(db, articleId);
  const detached = component.find((row) => row.id === articleId);
  if (!detached) return { head: null, domains: new Set() };
  db.prepare(`UPDATE articles SET cluster_id=NULL, is_original=0,
    cluster_latest=NULL, cluster_n=NULL WHERE id=?`).run(articleId);
  const repaired = rebuildRows(db, component.filter((row) => row.id !== articleId));
  repaired.domains.add(detached.domain);
  return repaired;
}

function exactClusterHead(db, dk, published, exclude = new Set()) {
  const rows = db.prepare(`SELECT id FROM articles
    WHERE dedupe_key=? AND published_at BETWEEN ? AND ?
    ORDER BY published_at, id`).all(
    dk, published - CLUSTER_WINDOW_MS, published + CLUSTER_WINDOW_MS,
  );
  const candidate = rows.find((row) => !exclude.has(row.id));
  if (!candidate) return null;
  const repaired = repairArticleCluster(db, candidate.id);
  refreshDomains(db, repaired.domains);
  return repaired.head;
}

function attachEditorialArticleToExactCluster(db, articleId, exclude = new Set()) {
  const row = db.prepare(`SELECT id, dedupe_key, published_at, domain
    FROM articles WHERE id=?`).get(articleId);
  if (!row) return { head: null, domains: new Set() };
  const affected = new Set([row.domain]);
  const head = exactClusterHead(db, row.dedupe_key, row.published_at,
    new Set([...exclude, articleId]));
  // Techmeme already supplies an editorially selected primary link. Generic
  // infrastructure headlines routinely share five template tokens across
  // unrelated companies ("has ... data center capacity ... backlog"). Fuzzy
  // clustering here would hide one vetted event under another. Exact URL was
  // resolved before insertion; only the full normalized-title key is safe for
  // automatically joining an editorial row.
  if (!head) return rebuildRows(db, [row]);
  const component = clusterComponent(db, head.id);
  addAll(affected, component.map((member) => member.domain));
  const rebuilt = rebuildRows(db, [...component, row]);
  addAll(rebuilt.domains, affected);
  return rebuilt;
}

function clearMergeVerdicts(db, articleId) {
  db.prepare('DELETE FROM merge_verdicts WHERE pair LIKE ? OR pair LIKE ?')
    .run(`${articleId}:%`, `%:${articleId}`);
}

function hasOtherReferences(db, articleId, source, sourceKey) {
  return Boolean(db.prepare(`SELECT 1 ok FROM editorial_references
    WHERE article_id=? AND (source != ? OR source_key != ?) LIMIT 1`)
    .get(articleId, source, sourceKey));
}

function retiredGuid(row) {
  return `retired-techmeme:${row.id}`;
}

/**
 * Delete only a generated Techmeme row. Exact-URL replacement is the sole case
 * where every old reference may safely move; otherwise snapshots keep a NULL
 * navigation link until their own pml is seen again.
 */
function removeTechmemeArticle(db, articleId, replacementId = null) {
  const row = db.prepare('SELECT * FROM articles WHERE id=?').get(articleId);
  if (!row || !ownsTechmemeArticle(row)) return new Set();
  const detached = detachArticle(db, articleId);
  const affected = detached.domains;
  let references = [];
  if (replacementId) {
    references = db.prepare(`SELECT source, value, genre, angle
      FROM editorial_references WHERE article_id=?`).all(articleId);
    db.prepare('UPDATE editorial_references SET article_id=? WHERE article_id=?')
      .run(replacementId, articleId);
  } else {
    db.prepare('UPDATE editorial_references SET article_id=NULL WHERE article_id=?').run(articleId);
  }
  db.prepare('DELETE FROM articles WHERE id=?').run(articleId);
  clearMergeVerdicts(db, articleId);
  affected.add(row.domain);

  if (replacementId) {
    // The removed row may have been the only pointer joining its members to a
    // separately clustered publisher row. Exact downstream URL identity proves
    // both remaining components are one story, so rebuild their union instead
    // of leaving the former members as an unrelated visible cluster.
    const replacementComponent = clusterComponent(db, replacementId);
    const residualComponent = detached.head
      ? clusterComponent(db, detached.head.id)
      : [];
    const rebuilt = rebuildRows(db, [...replacementComponent, ...residualComponent]);
    addAll(affected, rebuilt.domains);
    // Every historical selection survives on the publisher row with its own
    // floor as well as its self-contained reference snapshot.
    for (const reference of references) {
      addAll(affected, ensureEditorialFloor(db, replacementId, {
        relevance: 3, value: reference.value ?? 2, genre: reference.genre,
        angle: reference.angle, hits: [], source: reference.source,
      }));
    }
  }
  return affected;
}

function evictOwnedArticle(db, articleId, verdict, fallbackHits) {
  const affected = detachArticle(db, articleId).domains;
  db.prepare('DELETE FROM article_editorial_bases WHERE article_id=?').run(articleId);
  db.prepare(`UPDATE articles SET relevance=?, relevant=0, hits=?, value=0,
    genre='noise', value_src='editorial', cluster_id=id, is_original=1,
    cluster_latest=published_at, cluster_n=1 WHERE id=?`).run(
    verdict.relevance ?? 0, mergeHits('', verdict.hits || fallbackHits), articleId,
  );
  clearMergeVerdicts(db, articleId);
  return affected;
}

function mergeHits(current, incoming, source = null) {
  const values = new Set(String(current || '').split(',').filter(Boolean));
  for (const hit of incoming || []) if (hit) values.add(hit);
  if (source) values.add(`editorial:${source}`);
  return [...values].join(',');
}

/** Repair the selected cluster, then persist its display eligibility floor. */
function ensureEditorialFloor(db, articleId, floor, editorialOptions = {}) {
  const rebuilt = repairArticleCluster(db, articleId, editorialOptions);
  if (!rebuilt.head) return rebuilt.domains;
  applyEditorialFloorRows(db, articleId, rebuilt.head.id, floor, rebuilt.domains);
  return rebuilt.domains;
}

function applyEditorialFloorRows(db, articleId, headId, floor, domains) {
  const targetIds = new Set([Number(articleId), Number(headId)]);
  const get = db.prepare(`SELECT id, relevance, hits, angle, value, genre, domain
    FROM articles WHERE id=?`);
  const update = db.prepare(`UPDATE articles SET relevance=?, relevant=1, hits=?,
    angle=?, value=?, genre=?, value_src='editorial' WHERE id=?`);
  for (const id of targetIds) {
    const row = get.get(id);
    if (!row) continue;
    snapshotEditorialBase(db, id);
    const currentValue = Number(row.value ?? 0);
    const editorialValue = Number(floor.value ?? 2);
    const useEditorialShape = editorialValue >= currentValue;
    update.run(
      Math.max(Number(row.relevance || 0), Number(floor.relevance || 3)),
      mergeHits(row.hits, floor.hits, floor.source),
      useEditorialShape ? (floor.angle || row.angle) : row.angle,
      Math.max(currentValue, editorialValue),
      useEditorialShape ? (floor.genre || row.genre) : row.genre,
      id,
    );
    domains.add(row.domain);
  }
}

function snapshotEditorialBase(db, articleId) {
  db.prepare(`INSERT OR IGNORE INTO article_editorial_bases
      (article_id, relevance, relevant, hits, angle, value, genre, value_src)
    SELECT id, relevance, relevant, hits, angle, value, genre, value_src
    FROM articles WHERE id=? AND COALESCE(value_src, '') != 'editorial'`).run(articleId);
}

function restoreEditorialBase(db, articleId, domains) {
  const base = db.prepare('SELECT * FROM article_editorial_bases WHERE article_id=?').get(articleId);
  if (!base) return false;
  const row = db.prepare('SELECT domain FROM articles WHERE id=?').get(articleId);
  if (!row) {
    db.prepare('DELETE FROM article_editorial_bases WHERE article_id=?').run(articleId);
    return false;
  }
  db.prepare(`UPDATE articles SET relevance=?, relevant=?, hits=?, angle=?, value=?,
    genre=?, value_src=? WHERE id=?`).run(
    base.relevance, base.relevant, base.hits, base.angle, base.value,
    base.genre, base.value_src, articleId,
  );
  db.prepare('DELETE FROM article_editorial_bases WHERE article_id=?').run(articleId);
  domains.add(row.domain);
  return true;
}

function refreshDomains(db, domains) {
  for (const domain of domains || []) refreshDomainStats(db, domain);
}

function touchDomain(db, domain, now, relevant, isOriginal, lagMs) {
  db.prepare(`INSERT INTO domains(domain, first_seen_at, last_seen_at, articles, relevant, originals, lead_ms_sum, lead_n)
              VALUES (?,?,?,1,?,?,?,1)
              ON CONFLICT(domain) DO UPDATE SET
                first_seen_at = COALESCE(first_seen_at, excluded.first_seen_at),
                last_seen_at  = excluded.last_seen_at,
                articles      = articles + 1,
                relevant      = relevant + excluded.relevant,
                originals     = originals + excluded.originals,
                lead_ms_sum   = lead_ms_sum + excluded.lead_ms_sum,
                lead_n        = lead_n + 1`)
    .run(domain, now, now, relevant ? 1 : 0, isOriginal ? 1 : 0, -lagMs);
}

function ownsTechmemeArticle(row) {
  // Ownership is provenance, not destination. A normal publisher feed can
  // legitimately contain an article hosted on techmeme.com; its domain alone
  // is never permission to physically delete the row.
  return String(row?.shard || '').startsWith('feed:techmeme');
}

function editorialObserverRank(shard) {
  const id = String(shard?.id || '');
  if (id.includes('techmeme-river')) return 2;
  if (id.includes('techmeme-live') || shard?.feedFormat === 'techmeme-rss') return 1;
  return 0;
}

function compareEditorialObservation(incoming, current) {
  if (!current) return 1;
  if (incoming.observed_at !== current.observed_at) {
    return incoming.observed_at > current.observed_at ? 1 : -1;
  }
  if (incoming.observer_rank !== current.observer_rank) {
    return incoming.observer_rank > current.observer_rank ? 1 : -1;
  }
  const incomingIdentity = `${incoming.url}\0${incoming.title}`;
  const currentIdentity = `${current.url}\0${current.title}`;
  return incomingIdentity === currentIdentity ? 0 : (incomingIdentity > currentIdentity ? 1 : -1);
}

/** Recount the two domains touched by an in-place legacy/editorial rewrite. */
function refreshDomainStats(db, domain) {
  if (!domain) return;
  const row = db.prepare(`SELECT COUNT(*) articles,
      COALESCE(SUM(a.relevant), 0) relevant,
      COALESCE(SUM(a.is_original), 0) originals,
      COALESCE(SUM(CASE WHEN h.id IS NULL THEN 0 ELSE h.published_at - a.published_at END), 0) lead_ms_sum,
      COALESCE(SUM(CASE WHEN h.id IS NULL THEN 0 ELSE 1 END), 0) lead_n,
      MIN(a.first_seen_at) first_seen_at, MAX(a.first_seen_at) last_seen_at
    FROM articles a LEFT JOIN articles h ON h.id = a.cluster_id WHERE a.domain = ?`).get(domain);
  if (!row?.articles) {
    db.prepare(`UPDATE domains SET articles=0, relevant=0, originals=0,
      lead_ms_sum=0, lead_n=0 WHERE domain=?`).run(domain);
    return;
  }
  db.prepare(`INSERT INTO domains
      (domain, first_seen_at, last_seen_at, articles, relevant, originals, lead_ms_sum, lead_n)
    VALUES (?,?,?,?,?,?,?,?)
    ON CONFLICT(domain) DO UPDATE SET
      first_seen_at=MIN(COALESCE(domains.first_seen_at, excluded.first_seen_at), excluded.first_seen_at),
      last_seen_at=MAX(COALESCE(domains.last_seen_at, 0), excluded.last_seen_at),
      articles=excluded.articles, relevant=excluded.relevant, originals=excluded.originals,
      lead_ms_sum=excluded.lead_ms_sum, lead_n=excluded.lead_n`)
    .run(domain, row.first_seen_at, row.last_seen_at, row.articles, row.relevant,
      row.originals, row.lead_ms_sum, row.lead_n);
}
