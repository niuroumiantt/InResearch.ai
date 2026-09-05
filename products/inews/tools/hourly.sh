#!/usr/bin/env bash
# 所有来源共用的一轮:抓 → 备份 → 发布。无参数是 FT；也可传
# ``bloomberg`` / ``cnbc`` / ``wsj`` / ``reuters`` / ``axios``。
#
# **FT / Bloomberg / WSJ / Reuters / Axios 会使用一个可见的 Chrome 专用窗口。** 它们在
# browser/tiers.py 里是 manual 档；定时表已得到站长明确授权，并把专用窗口开关
# 写进 LaunchAgent。CNBC 是公开直抓；只有正文不完整时才走无头兜底。
#
# 固定分钟只能隔开正常轮。系统唤醒、手动按钮和异常长轮仍可能撞车，所以同一
# resource_group 还要共用一把跨站锁：daily_chrome 并发 1，headless 并发 1。
#
# 失败**如实失败**:不重试、不吞错。日志留在 LOG,launchd 的 stderr 也留着。
set -uo pipefail
ROOT=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
cd "$ROOT"
. "$ROOT/tools/lib/directory_lock.sh"

SUPPORTED_SITES=(ft bloomberg cnbc wsj reuters axios)
if [ "${1:-}" = "--list-sites" ]; then
  printf '%s\n' "${SUPPORTED_SITES[@]}"
  exit 0
fi

SITE=${1:-ft}
case "$SITE" in
  ft)
    DEFAULT_OUT=$ROOT/out/FT.COM
    DEFAULT_DEST=/srv/rawarticle/ft
    DEFAULT_LOG=$ROOT/out/hourly.log
    DEFAULT_LOCK=/tmp/inews-ft.lock
    DEFAULT_RESOURCE_GROUP=daily_chrome
    CRAWL_ARGS=(--site ft --group all --pages 1 --limit 0 --order newest)
    ;;
  bloomberg)
    DEFAULT_OUT=$ROOT/out/BLOOMBERG.COM
    DEFAULT_DEST=/srv/rawarticle/bloomberg
    DEFAULT_LOG=$ROOT/out/bloomberg-hourly.log
    DEFAULT_LOCK=/tmp/inews-bloomberg.lock
    DEFAULT_RESOURCE_GROUP=daily_chrome
    CRAWL_ARGS=(--site bloomberg --pages 1 --limit 0 --order newest)
    ;;
  cnbc)
    DEFAULT_OUT=$ROOT/out/CNBC.COM
    DEFAULT_DEST=/srv/rawarticle/cnbc
    DEFAULT_LOG=$ROOT/out/cnbc-hourly.log
    DEFAULT_LOCK=/tmp/inews-cnbc.lock
    DEFAULT_RESOURCE_GROUP=headless
    CRAWL_ARGS=(--site cnbc --pages 1 --limit 0 --order newest)
    ;;
  wsj)
    DEFAULT_OUT=$ROOT/out/WSJ.COM
    DEFAULT_DEST=/srv/rawarticle/wsj
    DEFAULT_LOG=$ROOT/out/wsj-hourly.log
    DEFAULT_LOCK=/tmp/inews-wsj.lock
    DEFAULT_RESOURCE_GROUP=daily_chrome
    CRAWL_ARGS=(--site wsj --pages 1 --limit 0 --order newest)
    ;;
  reuters)
    DEFAULT_OUT=$ROOT/out/REUTERS.COM
    DEFAULT_DEST=/srv/rawarticle/reuters
    DEFAULT_LOG=$ROOT/out/reuters-hourly.log
    DEFAULT_LOCK=/tmp/inews-reuters.lock
    DEFAULT_RESOURCE_GROUP=daily_chrome
    CRAWL_ARGS=(--site reuters --pages 1 --limit 0 --order newest)
    ;;
  axios)
    DEFAULT_OUT=$ROOT/out/AXIOS.COM
    DEFAULT_DEST=/srv/rawarticle/axios
    DEFAULT_LOG=$ROOT/out/axios-hourly.log
    DEFAULT_LOCK=/tmp/inews-axios.lock
    DEFAULT_RESOURCE_GROUP=daily_chrome
    # adapter 把站长指定的 artificial intelligence + Latest 固定成唯一入口，
    # 不接受其它关键词，避免定时参数漂移到泛搜索。
    CRAWL_ARGS=(--site axios --pages 1 --limit 0 --order newest)
    ;;
  *) echo "不认识的来源:$SITE;可选 ft、bloomberg、cnbc、wsj、reuters、axios" >&2; exit 2 ;;
esac

OUT=${RAW_OUT:-$DEFAULT_OUT}
DEST=${RAW_DEST:-$DEFAULT_DEST}
LOG=${INEWS_LOG:-$DEFAULT_LOG}
LOCK=${INEWS_LOCK:-$DEFAULT_LOCK}
PY=${PY:-$ROOT/.venv/bin/inews}
RESOURCE_GROUP=${INEWS_RESOURCE_GROUP:-$DEFAULT_RESOURCE_GROUP}
case "$RESOURCE_GROUP" in
  daily_chrome|headless) ;;
  *) echo "不认识的资源组:$RESOURCE_GROUP" >&2; exit 2 ;;
esac
RESOURCE_LOCK=${INEWS_RESOURCE_LOCK:-/tmp/inews-$RESOURCE_GROUP.lock}
RESOURCE_WAIT_SECONDS=${INEWS_RESOURCE_WAIT_SECONDS:-600}
RESOURCE_POLL_SECONDS=${INEWS_RESOURCE_POLL_SECONDS:-5}
DASHBOARD_LOCK=${INEWS_DASHBOARD_LOCK:-/tmp/inews-dashboard-publish.lock}
DASHBOARD_WAIT_SECONDS=${INEWS_DASHBOARD_WAIT_SECONDS:-120}
DASHBOARD_POLL_SECONDS=${INEWS_DASHBOARD_POLL_SECONDS:-2}

# 日常 Chrome 任务始终使用自己的哨兵窗口，不碰站长正在看的标签页。LaunchAgent
# 也显式写这个变量；这里的默认值覆盖按钮和命令行入口。
if [ "$RESOURCE_GROUP" = "daily_chrome" ]; then
  export YIDIAN_LOCAL_SYNC_DEDICATED_WINDOW=${YIDIAN_LOCAL_SYNC_DEDICATED_WINDOW:-1}
fi

mkdir -p "$(dirname "$LOG")"
log() { echo "$(date -Iseconds) $*" >> "$LOG"; }

# 锁:上一轮还没跑完就跳过这一轮。抓一轮可能比一小时长(翻页 + 逐篇取正文都在
# 限速),两个实例同时写台账会互相盖。
#
# macOS 用自带 lockf 锁住 fd，进程异常退出由内核释放；Linux 开发机回退 flock。
# 这既避开 macOS 没有 util-linux flock 的旧事故，也没有 mkdir stale-lock 的接管竞态。
SITE_LOCK_FD=9
RESOURCE_LOCK_FD=8
DASHBOARD_LOCK_FD=7
inews_lock_try "$LOCK" "站点轮($SITE)" "$SITE_LOCK_FD"
site_lock_code=$?
if [ "$site_lock_code" -ne 0 ]; then
  if [ "$site_lock_code" -eq 75 ]; then
    site_owner=$(inews_lock_holder "$LOCK")
    log "跳过:${site_owner} 还在跑"
    exit 0
  fi
  log "站点锁建立失败，退出码 ${site_lock_code}；本轮明确失败"
  exit "$site_lock_code"
fi
SITE_LOCK_HELD=1
RESOURCE_LOCK_HELD=0
DASHBOARD_LOCK_HELD=0
cleanup() {
  if [ "$DASHBOARD_LOCK_HELD" -eq 1 ]; then
    inews_lock_release "$DASHBOARD_LOCK" "$DASHBOARD_LOCK_FD"
  fi
  if [ "$RESOURCE_LOCK_HELD" -eq 1 ]; then
    inews_lock_release "$RESOURCE_LOCK" "$RESOURCE_LOCK_FD"
  fi
  if [ "$SITE_LOCK_HELD" -eq 1 ]; then
    inews_lock_release "$LOCK" "$SITE_LOCK_FD"
  fi
}
trap cleanup EXIT
trap 'exit 129' HUP
trap 'exit 130' INT
trap 'exit 143' TERM

# 同类浏览器有界排队。10 分钟小于相邻固定时段的 15 分钟：常见的几分钟拖尾能
# 等到，47 分钟这类异常轮不会让多个 shell 一直堆在机器上；超时以 EX_TEMPFAIL
# 明确失败，下一次定时轮仍会从同一入口带回尚未入库的新稿。
inews_lock_acquire "$RESOURCE_LOCK" "抓取 $SITE($RESOURCE_GROUP)" \
  "$RESOURCE_WAIT_SECONDS" "$RESOURCE_POLL_SECONDS" "$RESOURCE_LOCK_FD"
resource_code=$?
if [ "$resource_code" -ne 0 ]; then
  exit "$resource_code"
fi
RESOURCE_LOCK_HELD=1

# --pages 1:**每次定时轮要的是「上轮之后新出的」**,而那永远在第 1 页
# (搜索页按时间倒序；Load More 站仍在同一页内展开)。翻到第 5 页是在挖历史,
# 而历史只需要挖一次 —— 8-23 那轮
# 45 个词 × 5 页 + 分类页,光发现就开了两百多次窗口(每次之间还要限速 4 秒),
# 一轮拖到十几分钟,换回来的是同一批早就在台账里的稿子。
#
# 挖历史用手敲一次:`inews --group all --pages 20 --limit 0`。
# 时间地板仍然由 sites/ft.py 的 EARLIEST(2025-01-01)兜着,翻多少页都过不去。
#
# --limit 0:不设上限(9-01 站长指定)。base 已经建立、9-01 又砍掉九个只会
# 带来垃圾的词,每轮真正新出的就是个位数 —— 上限保护的场景不存在了,留着
# 反而会在断档恢复后把补课拖成好几轮。发现阶段仍然只翻第 1 页,天然有界;
# 真出洪水时锁会挡住下一轮,慢一点但不会互相踩。
log "开始:$SITE"
"$PY" "${CRAWL_ARGS[@]}" --out "$OUT" >> "$LOG" 2>&1
code=$?
log "抓取结束,退出码 $code"
inews_lock_release "$RESOURCE_LOCK" "$RESOURCE_LOCK_FD"
RESOURCE_LOCK_HELD=0

# 退出码 1 = 一篇都没命中(链路可能断了);2+ = 真崩了。两种都不发布:
# 宁可服务器上停在上一轮的样子,也不要拿一份可疑的产出盖掉它。
if [ "$code" -ne 0 ]; then
  log "退出码非 0,本轮不发布"
  exit "$code"
fi

# 先备份再发布:发布带 --delete,备份是本机这份正本唯一的安全网。
RAW_OUT="$OUT" bash "$ROOT/tools/backup.sh" >> "$LOG" 2>&1 || log "备份失败(继续发布)"

# 用例里不发布 —— 发布要走 ssh,那不是这个脚本要验证的东西。
if [ "${INEWS_SKIP_PUBLISH:-}" = "1" ]; then
  log "INEWS_SKIP_PUBLISH=1,跳过发布"
  exit 0
fi

RAW_OUT="$OUT" RAW_DEST="$DEST" bash "$ROOT/tools/publish.sh" >> "$LOG" 2>&1
site_code=$?
if [ "$site_code" -ne 0 ]; then
  log "来源页面发布失败,退出码 $site_code"
  exit "$site_code"
fi

# 各来源仍各有自己的清单与正文；后台只有这一份跨库视图。任一来源跑完都会
# 用各库最新台账重画并发布它，避免各正文来源各自展示半套事实。
# 两个资源组允许同时抓，但不能同时 rsync 同一份 Dashboard。
inews_lock_acquire "$DASHBOARD_LOCK" "发布统一后台($SITE)" \
  "$DASHBOARD_WAIT_SECONDS" "$DASHBOARD_POLL_SECONDS" "$DASHBOARD_LOCK_FD"
dashboard_lock_code=$?
if [ "$dashboard_lock_code" -ne 0 ]; then
  exit "$dashboard_lock_code"
fi
DASHBOARD_LOCK_HELD=1
RAW_OUT="$ROOT/out/DASHBOARD" RAW_DEST=/srv/rawarticle/dashboard \
  bash "$ROOT/tools/publish.sh" >> "$LOG" 2>&1
dashboard_code=$?
inews_lock_release "$DASHBOARD_LOCK" "$DASHBOARD_LOCK_FD"
DASHBOARD_LOCK_HELD=0
log "来源页面与统一后台发布结束,退出码 $dashboard_code"
exit "$dashboard_code"
