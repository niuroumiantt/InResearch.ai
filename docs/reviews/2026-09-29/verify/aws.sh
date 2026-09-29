#!/usr/bin/env bash
# 在 AWS 上跑。先 ssh ubuntu@ip-172-26-11-47，然后把本文件整段粘贴到终端（或 scp 后 bash aws.sh）。
# 只读：不改文件、不重启、不重跑 CI。结果同时打印并写到 ~/inresearch-verify-aws-<日期>.txt，可整份贴回。
set -u
OUT="$HOME/inresearch-verify-aws-$(date +%F).txt"
{
echo "==== 0 主机"; hostname; date -Is
if [ "$(hostname)" != ip-172-26-11-47 ]; then echo "不是 AWS 主机（期望 ip-172-26-11-47），停止"; exit 1; fi

echo; echo "==== 1 发布链（inresearch-only-deploy）"
sudo systemctl list-timers --all --no-pager | grep -E 'inresearch|ops-|infra-' || echo "(无匹配 timer)"
echo "-- status:"; sudo cat /var/lib/inresearch-ops/inresearch-only/status 2>/dev/null || echo "(无 status 文件)"
echo "-- applied:"; sudo cat /var/lib/inresearch-ops/inresearch-only/applied 2>/dev/null || echo "(无 applied 文件)"
echo "-- 源码 HEAD:"; sudo git -c safe.directory=/srv/sources/inresearch.ai -C /srv/sources/inresearch.ai log --oneline -1 2>/dev/null
echo "-- 遗骸 unit:"; systemctl list-units --all --no-pager | grep -E 'inresearch-deploy|autopull|yidian|inresearch-oa' || echo "(无)"

echo; echo "==== 2 容器、镜像、卷、只读根"
sudo docker inspect inresearch-host-inresearch-1 --format 'image={{.Config.Image}} health={{.State.Health.Status}} ro={{.HostConfig.ReadonlyRootfs}} started={{.State.StartedAt}}{{range .Mounts}}
mount {{.Source}} -> {{.Destination}} rw={{.RW}}{{end}}'
echo "-- compose 标签:"; sudo docker inspect inresearch-host-inresearch-1 --format '{{index .Config.Labels "com.docker.compose.project.config_files"}}'
echo "-- 内存上限（0 = 无）:"; sudo docker inspect inresearch-host-inresearch-1 --format '{{.HostConfig.Memory}}'

echo; echo "==== 3 健康检查：compose 探的是什么、/healthz 实际落到哪"
sudo docker inspect inresearch-host-inresearch-1 --format '{{json .Config.Healthcheck}}'; echo
sudo docker exec inresearch-host-inresearch-1 python3 -c "
import urllib.request as u
for p in ('/healthz','/index.html','/'):
    try:
        r=u.urlopen('http://127.0.0.1:8000'+p,timeout=5); print(p,'->',r.status,'landed_on',r.geturl())
    except Exception as e: print(p,'->',type(e).__name__,e)"

echo; echo "==== 4 备份：inresearch 运行数据在不在备份里"
echo "-- 最近三天备份目录:"; sudo ls /srv/inresearch-backups 2>/dev/null | grep -E '^20' | tail -3
LAST=$(sudo ls /srv/inresearch-backups 2>/dev/null | grep -E '^20' | tail -1)
[ -n "$LAST" ] && { echo "-- $LAST 里有哪些项目目录（若无 inresearch 即未覆盖）:"; sudo ls "/srv/inresearch-backups/$LAST"; }
echo "-- 恢复演练:"; sudo python3 -c "import json;d=json.load(open('/srv/inresearch-backups/last-restore-drill.json'));print(d.get('status'),d.get('finished_at') or d.get('at'))" 2>/dev/null || echo "(无演练记录)"
echo "-- 运行数据目录大小与文件数:"; sudo du -sh /srv/inresearch.ai/data /srv/inresearch.ai/reports /srv/inresearch.ai/logs 2>/dev/null; sudo find /srv/inresearch.ai/data -maxdepth 1 -type f | wc -l

echo; echo "==== 5 凭证落点（只看属主与权限，不看值）"
sudo stat -c '%U:%G %a %y %n' /srv/host/inresearch-host/.env.inresearch /srv/inresearch.ai/data/.reader_sync_token /srv/inresearch.ai/data/.hub_secret /root/.config/inresearch/git-credentials 2>&1
echo "-- .env.inresearch 里有哪些变量名（不打印值）:"; sudo sed -n 's/^\([A-Z_][A-Z0-9_]*\)=.*/\1/p' /srv/host/inresearch-host/.env.inresearch 2>/dev/null

echo; echo "==== 6 网络暴露面"
sudo ss -tlnp | grep -E ':80 |:443 |:8000 |:8789 ' || echo "(无监听匹配)"
echo "-- 响应头:"; curl -sI https://inresearch.ai/ | grep -iE '^(HTTP|strict-transport|x-content-type|x-frame|server|location)'
echo "-- robots.txt:"; curl -s -o /dev/null -w 'code=%{http_code} redirect=%{redirect_url}\n' https://inresearch.ai/robots.txt
echo "-- 公开只读四页 + supply 302 + whoami:"; for p in / /bom.html /ledger.html /report.html /supply.html /api/whoami; do printf '%s -> ' "$p"; curl -s -o /dev/null -w '%{http_code}\n' "https://inresearch.ai$p"; done
echo "-- DNS（从 AWS 看）:"; for n in inresearch.ai www.inresearch.ai inews.today www.inews.today; do printf '%s A=' "$n"; dig +short A "$n" | tr '\n' ' '; printf ' CNAME='; dig +short CNAME "$n" | tr '\n' ' '; echo; done; printf 'NS inresearch.ai='; dig +short NS inresearch.ai | tr '\n' ' '; echo
echo "-- Tailscale:"; tailscale status --self --peers=false 2>/dev/null | head -2 || echo "(无 tailscale CLI)"

echo; echo "==== 7 磁盘、镜像累积、日志"
df -h / | tail -1
echo "-- inresearch-app 镜像数与占用:"; sudo docker images inresearch-app --format '{{.Tag}} {{.Size}} {{.CreatedSince}}' | wc -l; sudo docker system df
echo "-- Caddy 日志与部署日志:"; sudo du -sh /var/log/caddy 2>/dev/null; sudo ls -la /var/log/inresearch-deploy.log 2>/dev/null
echo "-- 应用日志目录里 >20MB 的文件:"; sudo find /srv/inresearch.ai/logs -type f -size +20M -printf '%s %p\n' 2>/dev/null || echo "(无)"
echo "-- 遗留 OA 网络:"; sudo docker network ls | grep -E 'oa-' || echo "(无)"

echo; echo "==== 8 inews 采集统计（只读打开数据库）"
DB=$(sudo ls /srv/inews-data/*.sqlite3 /srv/inews-data/*.db 2>/dev/null | head -1)
echo "-- 数据库文件: ${DB:-未找到}"; sudo ls -la /srv/inews-data/ 2>/dev/null | grep -E 'sqlite3|\.db'
echo "-- inews 版本:"; sudo docker exec inresearch-host-inews-1 curl -fsS http://127.0.0.1:8789/api/version; echo
[ -n "$DB" ] && sudo python3 - "$DB" <<'PY'
import sqlite3,sys,time
db=sqlite3.connect(f"file:{sys.argv[1]}?mode=ro",uri=True)
now=int(time.time()*1000); d=86400000
def q(label,sql,*a):
    try: print(label, db.execute(sql,a).fetchall())
    except Exception as e: print(label, "查询失败:", e)
q("来源数·分片按车道", "SELECT lane,COUNT(*) FROM shard_policy GROUP BY lane")
q("来源数·域名按状态", "SELECT COALESCE(status,'observing'),COUNT(*) FROM domains GROUP BY 1")
q("来源健康·评估状态", "SELECT COALESCE(assessment_status,'new'),COUNT(*) FROM domains GROUP BY 1")
print("每日 入库/相关/价值>=2（近 7 天，按首次见到）:")
q("  ", "SELECT date(first_seen_at/1000,'unixepoch'),COUNT(*),SUM(relevant),SUM(CASE WHEN value>=2 THEN 1 ELSE 0 END) FROM articles WHERE first_seen_at>=? GROUP BY 1 ORDER BY 1", now-7*d)
q("失败率·近 24h 拉取 [总数, 失败(error或>=400), 304]", "SELECT COUNT(*),SUM(CASE WHEN error IS NOT NULL OR status>=400 THEN 1 ELSE 0 END),SUM(CASE WHEN status=304 THEN 1 ELSE 0 END) FROM fetches WHERE started_at>=?", now-d)
q("失败最多的分片（近 24h）", "SELECT shard,COUNT(*) FROM fetches WHERE started_at>=? AND (error IS NOT NULL OR status>=400) GROUP BY shard ORDER BY 2 DESC LIMIT 10", now-d)
q("限速·近 1h 非直连请求数（上限约 36/分 = 2160）", "SELECT COUNT(*) FROM fetches WHERE started_at>=? AND shard NOT LIKE 'direct:%'", now-3600000)
q("去重·近 7 天 [总数, 转载数]", "SELECT COUNT(*),SUM(CASE WHEN is_original=0 THEN 1 ELSE 0 END) FROM articles WHERE first_seen_at>=?", now-7*d)
q("聚簇·近 7 天相关文章 [簇数, 平均簇大小]", "SELECT COUNT(DISTINCT COALESCE(cluster_id,id)), ROUND(1.0*COUNT(*)/COUNT(DISTINCT COALESCE(cluster_id,id)),2) FROM articles WHERE first_seen_at>=? AND relevant=1", now-7*d)
q("编辑线·近 24h 选题状态", "SELECT COALESCE(selection_status,'-'),COUNT(*) FROM news_events WHERE last_updated>=? GROUP BY 1", now-d)
q("编辑线·近 24h 已选按展示角度", "SELECT display_angle,COUNT(*) FROM news_events WHERE selection_status='selected' AND last_updated>=? GROUP BY 1 ORDER BY 2 DESC", now-d)
q("翻译·近 24h 按后端", "SELECT provider,COUNT(*) FROM translations WHERE at>=? GROUP BY 1", now-d)
q("翻译·近 24h 已选故事中仍无中文标题的文章数", "SELECT COUNT(*) FROM articles a JOIN news_events e ON e.cluster_id=COALESCE(a.cluster_id,a.id) WHERE e.selection_status='selected' AND e.last_updated>=? AND (a.title_zh IS NULL OR a.title_zh='')", now-d)
PY
echo "-- 翻译兜底是否配置（只数变量名）:"; sudo grep -cE '^INEWS_TRANSLATION_FALLBACK_(PROVIDER|URL|KEY|MODEL)=.' /srv/host/inresearch-host/.env.inews 2>/dev/null
sudo docker exec inresearch-host-inews-1 sh -c 'test -f translation-backends.json && echo backends-file-present || echo default-chain'

echo; echo "==== 9 feed v2 字段命中率（第④问最关心的两个数）"
curl -s 'https://inews.today/api/feeds/datacenter?hours=168&limit=100' | python3 -c "
import json,sys,collections
p=json.load(sys.stdin); it=p.get('items',[])
print('条数',len(it),'有下一页',bool(p.get('next_cursor')),'窗口',p.get('window'))
print('event_type 非空',sum(1 for i in it if i.get('event_type')),collections.Counter(i.get('event_type') for i in it).most_common(6))
print('origin_pointer 非空',sum(1 for i in it if i.get('origin_pointer')))
print('editorial_pick 为真',sum(1 for i in it if i.get('editorial_pick')))
print('layer_tags 分布',dict(collections.Counter(l for i in it for l in (i.get('layer_tags') or []))))
print('有 title_zh',sum(1 for i in it if i.get('title_zh')))"
echo; echo "==== 完成，结果已写到 $OUT"
} 2>&1 | tee "$OUT"
