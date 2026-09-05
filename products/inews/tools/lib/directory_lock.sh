#!/usr/bin/env bash
# 跨进程文件锁。macOS 用系统自带的 lockf；Linux 测试/开发机回退到 flock。
#
# 锁落在调用方传入的文件描述符上，而不是靠「看 PID、删目录」猜旧进程是否还活着：
# 进程退出时内核会自动释放，两个等待者也不可能同时“接管”同一把锁。锁文件本身
# 故意保留，绝不能在释放后 unlink —— 否则新旧 inode 会让两个进程各锁各的。

_inews_lock_backend() {
  if [ -x "${INEWS_LOCKF_BIN:-/usr/bin/lockf}" ]; then
    printf '%s\n' lockf
    return 0
  fi
  if [ -x /usr/bin/flock ]; then
    printf '%s\n' flock
    return 0
  fi
  if command -v flock >/dev/null 2>&1; then
    printf '%s\n' flock-path
    return 0
  fi
  return 69
}

_inews_lock_fd_try() {
  local fd=$1 backend command_path
  backend=$(_inews_lock_backend) || return $?
  case "$backend" in
    lockf)
      command_path=${INEWS_LOCKF_BIN:-/usr/bin/lockf}
      "$command_path" -t 0 "$fd" >/dev/null 2>&1
      ;;
    flock)
      /usr/bin/flock -n "$fd" >/dev/null 2>&1
      ;;
    flock-path)
      flock -n "$fd" >/dev/null 2>&1
      ;;
  esac
}

_inews_lock_mtime() {
  stat -f %m "$1" 2>/dev/null || stat -c %Y "$1" 2>/dev/null || echo 0
}

_inews_migrate_legacy_lock_dir() {
  local path=$1 owner_pid age now modified
  [ -d "$path" ] || return 0
  owner_pid=$(cat "$path/pid" 2>/dev/null || echo "")
  if [ -n "$owner_pid" ] && kill -0 "$owner_pid" 2>/dev/null; then
    return 75
  fi
  # 兼容升级前的 mkdir 锁。没有 pid 的新目录先当活锁，避免撞上旧脚本刚 mkdir、
  # 尚未来得及写 pid 的极短窗口；这段迁移在目录消失后永远不会再走。
  if [ -z "$owner_pid" ]; then
    now=$(date +%s)
    modified=$(_inews_lock_mtime "$path")
    age=$((now - modified))
    [ "$age" -ge 30 ] || return 75
  fi
  rm -f "$path/pid" "$path/owner" "$path/started_at"
  if rmdir "$path" 2>/dev/null; then
    log "旧目录锁 ${path} 的持有者(${owner_pid:-未知})已退出，迁移为内核文件锁"
  elif [ -d "$path" ]; then
    return 75
  fi
  return 0
}

_inews_lock_open_fd() {
  local path=$1 fd=$2 parent
  parent=$(dirname "$path")
  mkdir -p "$parent" || return 73
  _inews_migrate_legacy_lock_dir "$path" || return $?
  # fd 只接受调用方写死的数字；路径在第二次解析时仍处于双引号内。
  case "$fd" in
    ''|*[!0-9]*) return 64 ;;
  esac
  eval "exec ${fd}>>\"\$path\"" || return 73
}

_inews_lock_close_fd() {
  local fd=$1
  eval "exec ${fd}>&-" 2>/dev/null || true
}

inews_lock_holder() {
  local path=$1 holder
  holder=$(cat "$path" 2>/dev/null || echo "")
  if [ -n "$holder" ]; then
    printf '%s\n' "$holder"
  else
    printf '%s\n' "另一轮"
  fi
}

inews_lock_try() {
  local path=$1 owner=$2 fd=$3 open_code lock_code previous
  previous=$(cat "$path" 2>/dev/null || echo "")
  _inews_lock_open_fd "$path" "$fd"
  open_code=$?
  [ "$open_code" -eq 0 ] || return "$open_code"
  _inews_lock_fd_try "$fd"
  lock_code=$?
  if [ "$lock_code" -eq 0 ]; then
    if [ -n "$previous" ]; then
      log "资源锁 ${path} 没有活跃内核持有者，接管上次记录:${previous}"
    fi
    printf '%s\t%s\t%s\n' "$$" "$owner" "$(date -Iseconds)" > "$path"
    return 0
  fi
  _inews_lock_close_fd "$fd"
  # lockf 的“已锁”是 EX_TEMPFAIL(75)，flock 通常是 1；统一成 75。其它错误
  # 不能冒充“上一轮还在跑”，否则又会静默跳过。
  case "$lock_code" in
    1|75) return 75 ;;
    *)
      log "无法使用系统文件锁保护 ${path}（退出码 ${lock_code}）"
      return 69
      ;;
  esac
}

inews_lock_acquire() {
  local path=$1 owner=$2 wait_seconds=${3:-0} poll_seconds=${4:-5} fd=$5
  local began=$SECONDS announced=0 held_by lock_code
  while true; do
    inews_lock_try "$path" "$owner" "$fd"
    lock_code=$?
    if [ "$lock_code" -eq 0 ]; then
      if [ "$announced" -eq 1 ]; then
        log "资源已释放:${owner} 继续运行"
      fi
      return 0
    fi
    [ "$lock_code" -eq 75 ] || return "$lock_code"
    if [ "$announced" -eq 0 ]; then
      held_by=$(inews_lock_holder "$path")
      log "资源忙:${owner} 等待 ${held_by} 释放 ${path}（最多 ${wait_seconds} 秒）"
      announced=1
    fi
    if [ $((SECONDS - began)) -ge "$wait_seconds" ]; then
      log "资源等待超时:${owner} 未运行；下一个固定时段会再次尝试"
      return 75
    fi
    sleep "$poll_seconds"
  done
}

inews_lock_release() {
  local path=$1 fd=$2
  # 清掉仅供人看的持有记录，但保留 inode；关 fd 就是原子的内核解锁。
  : > "$path" 2>/dev/null || true
  _inews_lock_close_fd "$fd"
}
