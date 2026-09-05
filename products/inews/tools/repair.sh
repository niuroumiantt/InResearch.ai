#!/usr/bin/env bash
# 手动修复未抓取:把台账里记着「取正文失败」的那些**全部**重取一遍,然后发布。
#
# 和每小时那一轮的分工:
#   hourly*.sh   找新稿子;顺带按 6/24/72 小时的退避重试少数几篇失败的
#   repair.sh    **不搜索**,只重取失败的,而且不看退避 —— 试满自动重试的那些
#                只等这个入口。这就是清单页上「修复未抓取」按钮背后的那条命令。
#
# 为什么要有「不看退避」的一条路:退避是为了别每轮白开几十个窗口,不是判它死刑。
# 站长看到某几篇一直空着,想立刻再试一次时,得有个地方按 —— 就是这里。
#
#   bash tools/repair.sh            # 默认 FT
#   bash tools/repair.sh bloomberg
#   bash tools/repair.sh cnbc
#   bash tools/repair.sh wsj
#   bash tools/repair.sh reuters
#   bash tools/repair.sh axios
#
# FT / Bloomberg / WSJ / Reuters / Axios 会打开可见 Chrome；CNBC 公开直抓，
# 失败时只做无头兜底。
# 失败如实失败:不重试、不吞错。
set -uo pipefail
ROOT=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
cd "$ROOT"
. "$ROOT/tools/lib/directory_lock.sh"

SITE=${1:-ft}
case "$SITE" in
  ft)
    OUT=${RAW_OUT:-$ROOT/out/FT.COM}
    DEST=${RAW_DEST:-/srv/rawarticle/ft}
    LOCK=${INEWS_LOCK:-/tmp/inews-ft.lock}
    LOG=${INEWS_LOG:-$ROOT/out/hourly.log}
    DEFAULT_RESOURCE_GROUP=daily_chrome
    ;;
  bloomberg)
    OUT=${RAW_OUT:-$ROOT/out/BLOOMBERG.COM}
    DEST=${RAW_DEST:-/srv/rawarticle/bloomberg}
    LOCK=${INEWS_LOCK:-/tmp/inews-bloomberg.lock}
    LOG=${INEWS_LOG:-$ROOT/out/bloomberg-hourly.log}
    DEFAULT_RESOURCE_GROUP=daily_chrome
    ;;
  cnbc)
    OUT=${RAW_OUT:-$ROOT/out/CNBC.COM}
    DEST=${RAW_DEST:-/srv/rawarticle/cnbc}
    LOCK=${INEWS_LOCK:-/tmp/inews-cnbc.lock}
    LOG=${INEWS_LOG:-$ROOT/out/cnbc-hourly.log}
    DEFAULT_RESOURCE_GROUP=headless
    ;;
  wsj)
    OUT=${RAW_OUT:-$ROOT/out/WSJ.COM}
    DEST=${RAW_DEST:-/srv/rawarticle/wsj}
    LOCK=${INEWS_LOCK:-/tmp/inews-wsj.lock}
    LOG=${INEWS_LOG:-$ROOT/out/wsj-hourly.log}
    DEFAULT_RESOURCE_GROUP=daily_chrome
    ;;
  reuters)
    OUT=${RAW_OUT:-$ROOT/out/REUTERS.COM}
    DEST=${RAW_DEST:-/srv/rawarticle/reuters}
    LOCK=${INEWS_LOCK:-/tmp/inews-reuters.lock}
    LOG=${INEWS_LOG:-$ROOT/out/reuters-hourly.log}
    DEFAULT_RESOURCE_GROUP=daily_chrome
    ;;
  axios)
    OUT=${RAW_OUT:-$ROOT/out/AXIOS.COM}
    DEST=${RAW_DEST:-/srv/rawarticle/axios}
    LOCK=${INEWS_LOCK:-/tmp/inews-axios.lock}
    LOG=${INEWS_LOG:-$ROOT/out/axios-hourly.log}
    DEFAULT_RESOURCE_GROUP=daily_chrome
    ;;
  *)
    echo "不认识的站:$SITE(只有 ft / bloomberg / cnbc / wsj / reuters / axios)" >&2
    exit 2
    ;;
esac
PY=${PY:-$ROOT/.venv/bin/inews}
PUBLISH_SH=${INEWS_PUBLISH_SH:-$ROOT/tools/publish.sh}
BACKUP_SH=${INEWS_BACKUP_SH:-$ROOT/tools/backup.sh}
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
if [ "$RESOURCE_GROUP" = "daily_chrome" ]; then
  export YIDIAN_LOCAL_SYNC_DEDICATED_WINDOW=${YIDIAN_LOCAL_SYNC_DEDICATED_WINDOW:-1}
fi

mkdir -p "$(dirname "$LOG")"
log() { echo "$(date -Iseconds) $*" >> "$LOG"; }

# **和抓取共用同一把站点锁**:两者都写同一份台账,一起跑会互相盖。锁由内核
# 随进程生命周期释放，不靠删除 stale 目录来接管。
SITE_LOCK_FD=9
RESOURCE_LOCK_FD=8
DASHBOARD_LOCK_FD=7
inews_lock_try "$LOCK" "修复轮($SITE)" "$SITE_LOCK_FD"
site_lock_code=$?
if [ "$site_lock_code" -ne 0 ]; then
  if [ "$site_lock_code" -eq 75 ]; then
    site_owner=$(inews_lock_holder "$LOCK")
    log "修复跳过:${site_owner} 还在跑"
    exit 0
  fi
  log "站点锁建立失败，退出码 ${site_lock_code}；修复轮明确失败"
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

inews_lock_acquire "$RESOURCE_LOCK" "修复 $SITE($RESOURCE_GROUP)" \
  "$RESOURCE_WAIT_SECONDS" "$RESOURCE_POLL_SECONDS" "$RESOURCE_LOCK_FD"
resource_code=$?
if [ "$resource_code" -ne 0 ]; then
  exit "$resource_code"
fi
RESOURCE_LOCK_HELD=1

# --limit 0:失败的有几篇就修几篇。这是手动按下去的,不该被一个默认上限拦腰砍断。
log "开始修复未抓取($SITE)"
"$PY" --site "$SITE" --retry-failed --limit 0 --out "$OUT" >> "$LOG" 2>&1
code=$?
log "修复结束,退出码 $code"
inews_lock_release "$RESOURCE_LOCK" "$RESOURCE_LOCK_FD"
RESOURCE_LOCK_HELD=0

if [ "$code" -ne 0 ]; then
  log "退出码非 0,本轮不发布"
  exit "$code"
fi

if [ "${INEWS_SKIP_PUBLISH:-}" = "1" ]; then
  log "INEWS_SKIP_PUBLISH=1,跳过发布"
  exit 0
fi

# 与每小时轮同一条发布纪律：先留本机备份；来源页失败就保留服务器上一版，
# 而且把真实非零退出码交还给按钮/监听，不能让最后一条 log 把失败洗成成功。
RAW_OUT="$OUT" bash "$BACKUP_SH" >> "$LOG" 2>&1 || log "备份失败(继续发布)"
RAW_OUT="$OUT" RAW_DEST="$DEST" bash "$PUBLISH_SH" >> "$LOG" 2>&1
site_code=$?
if [ "$site_code" -ne 0 ]; then
  log "来源页面发布失败,退出码 $site_code"
  exit "$site_code"
fi

# retry-failed 同样会重画跨库 Dashboard；来源修好后立刻发布它，避免统一后台
# 仍把这批正文报作失败或积压。
inews_lock_acquire "$DASHBOARD_LOCK" "发布统一后台修复结果($SITE)" \
  "$DASHBOARD_WAIT_SECONDS" "$DASHBOARD_POLL_SECONDS" "$DASHBOARD_LOCK_FD"
dashboard_lock_code=$?
if [ "$dashboard_lock_code" -ne 0 ]; then
  exit "$dashboard_lock_code"
fi
DASHBOARD_LOCK_HELD=1
RAW_OUT="$ROOT/out/DASHBOARD" RAW_DEST=/srv/rawarticle/dashboard \
  bash "$PUBLISH_SH" >> "$LOG" 2>&1
dashboard_code=$?
inews_lock_release "$DASHBOARD_LOCK" "$DASHBOARD_LOCK_FD"
DASHBOARD_LOCK_HELD=0
log "来源页面与统一后台发布结束,退出码 $dashboard_code"
exit "$dashboard_code"
