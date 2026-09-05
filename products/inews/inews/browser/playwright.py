"""通过隔离 Playwright Chromium 与 BPC 扩展读取付费私站正文。"""
from __future__ import annotations

import atexit
import logging
import os
import queue
import re
import sys
import tempfile
import threading
import time
from concurrent.futures import Future
from dataclasses import dataclass
from pathlib import Path

from inews.browser.contract import (
    BODY_WORD_COUNT_META_SELECTORS,
    SITE_DOMAINS,
    BrowserBypassError,
    body_coverage_is_enough,
    cookies_from_header,
    count_body_words,
    raw_html_marker_matches,
    site_for_url,
)
from inews.browser.profile import (
    PROJECT_ROOT,
    chrome_profile_path,
    extension_path,
    snapshot_chrome_profile,
)

log = logging.getLogger("inews.browser.playwright")

SHARED_BROWSERS = PROJECT_ROOT / ".playwright-browsers"
if "PLAYWRIGHT_BROWSERS_PATH" not in os.environ and SHARED_BROWSERS.is_dir():
    os.environ["PLAYWRIGHT_BROWSERS_PATH"] = str(SHARED_BROWSERS)

ARTICLE_SELECTORS = (
    "article#article-body",
    "div.article__content-body",
    "div[data-component='article-body']",
    "div[data-component='body-content']",
    "div.body-content",
    "div[class*='body-content']",
    "div.n-content-body",
    "div[style*='article-body']",
    "div.n-layout__row--content",
    "article",
    "main",
)
# 只有真人能过的那一类拦截(滑块、机器人验证)。与 BARRIER_RX 分开:订阅墙
# 换条路还有戏,这一类必须请人来一趟,该做的处置完全不同。
HUMAN_CHECK_RX = re.compile(
    r"(are you a robot|unusual activity|verification required|"
    r"slide right|press and hold|verify (?:that )?you are human|"
    r"just a moment|checking your browser|"
    r"enable javascript and cookies to continue)",
    re.IGNORECASE,
)
BARRIER_RX = re.compile(
    r"(subscribe to unlock|choose your subscription|complete your subscription|"
    r"subscribe to read|sign in to keep reading|register to continue|"
    r"before it.s here, it.s on the bloomberg terminal|"
    r"data-trackable=.barrier|barrier-page|are you a robot|unusual activity|"
    r"just a moment|verify (?:that )?you are human|checking your browser|"
    r"enable javascript and cookies to continue)",
    re.IGNORECASE,
)


def bypass_status() -> dict[str, object]:
    """探测隔离浏览器链路；不向网页暴露本机绝对路径."""
    if extension_path() is None:
        return {
            "ok": False,
            "note": (
                "未找到 Bypass Paywalls Clean 扩展"
                "(请配置 INEWS_BYPASS_EXTENSION_PATH)"
            ),
        }
    try:
        import playwright.sync_api  # noqa: F401
    except ImportError:
        return {"ok": False, "note": "未安装 Playwright(请重新安装 requirements.txt)"}
    profile_note = "，将镜像当前 Chrome 的 BPC 状态" if chrome_profile_path() else ""
    return {
        "ok": True,
        "note": f"本地 Bypass Paywalls Clean 浏览器链路已配置{profile_note}",
    }


def public_status() -> dict[str, object]:
    """公开站无头通道只需要 Playwright，不读取 Chrome profile 或 BPC 扩展。"""
    try:
        import playwright.sync_api  # noqa: F401
    except ImportError:
        return {"ok": False, "note": "未安装 Playwright(请重新安装 requirements.txt)"}
    return {"ok": True, "note": "公开 HTTPS 直抓；失败时使用隔离的无头 Chromium"}


@dataclass(frozen=True)
class FetchRequest:
    site: str
    url: str
    cookie: str
    min_chars: int
    timeout_seconds: int
    future: Future
    # 验收必须与日常 Chrome 通道同强度。少了 min_words,「无头优先」就成了
    # 「优先走一条门槛更低的路」—— 那是拿导语冒充正文,不是换条路再试。
    min_words: int = 0
    # 页面若自报全文词数，实际正文至少覆盖这个比例；WSJ 用它识别够长但仍被
    # 截断的付费预览。0 表示该站不启用比例验收。
    min_coverage: float = 0.0
    # 各站声明的正文容器;留空用通用表。同理:通用表比该站自己声明的宽,
    # 拿它取正文可能刮到导航或推荐位。
    selectors: tuple[str, ...] = ()
    paragraph_selectors: tuple[str, ...] = ()
    reject_patterns: tuple[str, ...] = ()
    settle_polls: int = 1
    # 非空 = 这是一次**列表页**读取,完成判据换成这段自证脚本(与日常 Chrome
    # 共用 browser_contract.listing_probe_script)。列表页与正文的「好了没有」
    # 是两个问题:前者要等结果容器与链接集合稳定,后者要等正文字数词数达标。
    probe: str = ""


class BrowserWorker:
    """专用线程串行持有并复用 Playwright/Chromium."""

    def __init__(self) -> None:
        self._requests: queue.Queue[FetchRequest | None] = queue.Queue()
        self._start_lock = threading.Lock()
        self._thread: threading.Thread | None = None

    def fetch(
        self,
        url: str,
        *,
        site: str,
        cookie: str,
        min_chars: int,
        timeout_seconds: int,
        min_words: int = 0,
        min_coverage: float = 0.0,
        selectors: tuple[str, ...] = (),
        paragraph_selectors: tuple[str, ...] = (),
        reject_patterns: tuple[str, ...] = (),
        settle_polls: int = 1,
    ) -> tuple[str, str]:
        # 边界是 SITE_DOMAINS,不是写死的站名。此前这里挡着 {"ft","bloomberg"},
        # 于是「无头优先」只惠及两家专属模块站,其余 12 家声明式站点全程弹窗
        # (2026-08-07 站长实测:浏览器还在往眼前跳)。放行范围没有变宽 ——
        # SITE_DOMAINS 本来就是本地浏览器通道的安全边界,site_for_url 早已在查它。
        if site not in SITE_DOMAINS or site_for_url(url) != site:
            raise BrowserBypassError("BPC 浏览器只允许读取已登记私站的 HTTPS 页面")
        status = bypass_status()
        if not status["ok"]:
            raise BrowserBypassError(str(status["note"]))
        timeout_seconds = max(15, min(int(timeout_seconds), 180))
        future: Future = Future()
        self._ensure_started()
        self._requests.put(
            FetchRequest(
                site, url, cookie, min_chars, timeout_seconds, future,
                min_words=max(0, int(min_words)),
                min_coverage=max(0.0, float(min_coverage)),
                selectors=tuple(selectors),
                paragraph_selectors=tuple(paragraph_selectors),
                reject_patterns=tuple(reject_patterns),
                settle_polls=max(1, int(settle_polls)),
            )
        )
        try:
            return future.result(timeout=timeout_seconds + 45)
        except TimeoutError as exc:
            raise BrowserBypassError(
                f"BPC 浏览器工作线程超时({timeout_seconds + 45} 秒)"
            ) from exc

    def fetch_listing(
        self,
        url: str,
        *,
        site: str,
        probe: str,
        timeout_seconds: int,
    ) -> tuple[str, str]:
        """列表页读取:同一条线程、同一个 context,只是完成判据不同。"""
        if site not in SITE_DOMAINS or site_for_url(url) != site:
            raise BrowserBypassError("BPC 浏览器只允许读取已登记私站的 HTTPS 页面")
        status = bypass_status()
        if not status["ok"]:
            raise BrowserBypassError(str(status["note"]))
        timeout_seconds = max(15, min(int(timeout_seconds), 180))
        future: Future = Future()
        self._ensure_started()
        self._requests.put(
            FetchRequest(site, url, "", 0, timeout_seconds, future, probe=probe)
        )
        try:
            return future.result(timeout=timeout_seconds + 45)
        except TimeoutError as exc:
            raise BrowserBypassError(
                f"BPC 浏览器工作线程超时({timeout_seconds + 45} 秒)"
            ) from exc

    def _ensure_started(self) -> None:
        with self._start_lock:
            if self._thread and self._thread.is_alive():
                return
            self._thread = threading.Thread(
                target=self._run,
                name="paywall-bypass-browser",
                daemon=True,
            )
            self._thread.start()

    def _run(self) -> None:
        playwright = context = None
        try:
            from playwright.sync_api import sync_playwright

            while True:
                request = self._requests.get()
                if request is None:
                    return
                try:
                    if context is None:
                        playwright = sync_playwright().start()
                        context = self._launch(playwright)
                    result = self._fetch_one(context, request)
                # 这里没有吞:异常被包成 BrowserBypassError 交回调用方的 future。
                # 宽捕是必需的 —— 工作线程死掉的话,等在 future 上的调用方会永远挂住。
                except Exception as exc:  # noqa: BLE001 原样转交调用方,线程绝不能死
                    request.future.set_exception(
                        exc
                        if isinstance(exc, BrowserBypassError)
                        else BrowserBypassError(
                            f"BPC 浏览器失败:{type(exc).__name__}: {exc}"
                        )
                    )
                    if context is None and playwright is not None:
                        playwright.stop()
                        playwright = None
                    elif context is not None and self._context_closed(context):
                        context = None
                        if playwright is not None:
                            playwright.stop()
                            playwright = None
                else:
                    request.future.set_result(result)
        finally:
            self._close_drivers(context, playwright)

    @staticmethod
    def _close_drivers(context, playwright) -> None:
        if context is not None:
            try:
                context.close()
            except Exception as exc:  # noqa: BLE001 收尾失败不许盖掉正在上抛的真错误
                log.debug("关闭 BPC context 失败:%s", exc)
        if playwright is not None:
            try:
                playwright.stop()
            except Exception as exc:  # noqa: BLE001 同上:收尾失败不许盖掉真错误
                log.debug("停止 BPC Playwright 失败:%s", exc)

    @staticmethod
    def _context_closed(context) -> bool:
        try:
            return not context.pages and not context.service_workers
        except Exception:  # noqa: BLE001 连「它关了没」都问不出来,就当它关了并重建
            return True

    @staticmethod
    def _runtime_profile() -> Path:
        configured = (
            os.getenv("INEWS_BYPASS_PROFILE_DIR", "").strip()
            or os.getenv("FT_BYPASS_PROFILE_DIR", "").strip()
        )
        if configured:
            return Path(configured).expanduser().resolve()
        return Path(tempfile.mkdtemp(prefix=f"paywall-bpc-{os.getpid()}-"))

    # 默认无头 —— **包括 macOS**。此前默认是 `platform.system() != "Darwin"`,
    # 于是管理员 Mac 上每 5 分钟弹一次浏览器抢焦点(LaunchAgent StartInterval=300
    # + ADR-0017 在线自动排队,合起来就是"一直在弹")。那句判断从来没被评估过,
    # INVARIANTS 与 STATUS 都把它记成"推迟,单独评估"。
    #
    # 2026-08-07 实测判定(最小 MV3 扩展 + Playwright 1.61):
    #   · 无头 + **完整 Chromium**(新版 headless)→ 扩展加载成功 ✅
    #   · 无头 + headless_shell                  → service worker 起不来 ❌
    # 所以能不能无头,取决于**用哪个二进制**,与操作系统无关。
    #
    # 这也是 `_launch` 里 channel 默认 "chromium" 那行的隐藏契约:它让 Playwright
    # 取完整 Chromium 而不是 headless_shell。谁把 INEWS_BYPASS_BROWSER_CHANNEL
    # 改成会落到 headless_shell 的值,扩展就静悄悄不加载了 —— 好在 `_verify_extension`
    # 会当场抛错,不会变成"抓回一堆付费墙残页"。
    #
    # 留 INEWS_BYPASS_HEADLESS=0 给人工调试:要亲眼看浏览器在干什么的时候用。
    @staticmethod
    def _headless() -> bool:
        configured = (
            os.getenv("INEWS_BYPASS_HEADLESS", "").strip()
            or os.getenv("FT_BYPASS_HEADLESS", "").strip()
        ).lower()
        if configured:
            return configured not in {"0", "false", "no", "off"}
        return True

    @classmethod
    def _launch(cls, playwright):
        extension = extension_path()
        if extension is None:
            raise BrowserBypassError("启动前扩展目录已不存在")
        profile = cls._runtime_profile()
        profile.mkdir(parents=True, exist_ok=True)
        source_profile = chrome_profile_path()
        if source_profile is not None:
            mirrored = snapshot_chrome_profile(source_profile, profile)
            # 打到 stderr 而不是 log.info:这个数字一直存在,但没人看得见它,
            # 于是一次「0 条 Cookie」让站长和我对着 HTTP 401 猜了两轮。
            print(
                f"[bypass] 已从 Chrome profile={source_profile.name} 镜像:"
                f"扩展文件 {mirrored['settings_files']} 个、"
                f"放行域 Cookie {mirrored['cookie_count']} 条"
                + (f";⚠ {mirrored['cookie_note']}" if mirrored["cookie_note"] else ""),
                file=sys.stderr, flush=True,
            )
        context = playwright.chromium.launch_persistent_context(
            str(profile),
            channel=(
                os.getenv("INEWS_BYPASS_BROWSER_CHANNEL", "").strip()
                or "chromium"
            ),
            headless=cls._headless(),
            locale="en-US",
            viewport={"width": 1365, "height": 1000},
            ignore_default_args=["--enable-automation"],
            args=[
                f"--disable-extensions-except={extension}",
                f"--load-extension={extension}",
                "--profile-directory=Default",
                "--disable-blink-features=AutomationControlled",
            ],
            handle_sigint=False,
            handle_sigterm=False,
            handle_sighup=False,
        )
        cls._verify_extension(context)
        return context

    @staticmethod
    def _verify_extension(context) -> None:
        context.add_init_script(
            "Object.defineProperty(navigator, 'webdriver', {get: () => undefined});"
        )
        if not context.service_workers:
            try:
                context.wait_for_event("serviceworker", timeout=15_000)
            except Exception as exc:
                context.close()
                raise BrowserBypassError(
                    "Chromium 已启动，但 BPC 扩展未加载"
                ) from exc
        for opened_page in context.pages:
            opened_page.close()

    @staticmethod
    def _article_html(
        page,
        min_chars: int,
        min_words: int = 0,
        min_coverage: float = 0.0,
        selectors: tuple[str, ...] = (),
        paragraph_selectors: tuple[str, ...] = (),
        reject_patterns: tuple[str, ...] = (),
        probe_diagnostic: dict[str, object] | None = None,
    ) -> tuple[str, str, str] | None:
        # 结构标记必须从整页 HTML 看；但 BPC 恢复全文后 WSJ 仍保留该 class，
        # 所以它只会把覆盖率门槛提高到共享的 90%，不再一票否决。
        try:
            page_html = page.content()
        except Exception as exc:  # noqa: BLE001 页面还在导航时下一轮再试
            log.debug("读取整页 HTML 失败:%s", exc)
            return None
        raw_marker = raw_html_marker_matches(page_html, reject_patterns)

        declared_words = 0
        for selector in BODY_WORD_COUNT_META_SELECTORS:
            locator = page.locator(selector).first
            try:
                raw = locator.get_attribute("content", timeout=500) if locator.count() else ""
                parsed = int(float(str(raw or "").strip()))
            except (TypeError, ValueError):
                continue
            except Exception as exc:  # noqa: BLE001 元数据坏了不能阻断正文候选
                log.debug("读取全文词数 %s 失败:%s", selector, exc)
                continue
            if parsed > 0:
                declared_words = parsed
                break

        if probe_diagnostic is not None:
            probe_diagnostic.update(
                chars=0,
                words=0,
                declared=declared_words,
                raw_marker=raw_marker,
            )

        for selector in (selectors or ARTICLE_SELECTORS):
            locator = page.locator(selector).first
            try:
                if locator.count() == 0:
                    continue
                if paragraph_selectors:
                    nodes = locator.locator(", ".join(paragraph_selectors))
                    text = "\n\n".join(
                        part.strip()
                        for part in nodes.all_inner_texts()
                        if part.strip()
                    )
                else:
                    text = locator.inner_text(timeout=1_000).strip()
            except Exception as exc:  # noqa: BLE001 逐个选择器试探,这个不行就下一个
                log.debug("读取 BPC 候选容器 %s 失败:%s", selector, exc)
                continue
            words = count_body_words(text)
            if probe_diagnostic is not None:
                probe_diagnostic["chars"] = max(
                    int(probe_diagnostic["chars"]), len(text)
                )
                probe_diagnostic["words"] = max(
                    int(probe_diagnostic["words"]), words
                )
            enough_coverage = body_coverage_is_enough(
                words,
                declared_words,
                min_coverage,
                raw_marker=raw_marker,
            )
            if (
                len(text) >= min_chars
                and words >= min_words
                and enough_coverage
                and not BARRIER_RX.search(text)
            ):
                return page_html, page.url, text
        return None

    @staticmethod
    def _diagnostic(
        page,
        http_diagnostic: str,
        article_diagnostic: dict[str, object] | None = None,
    ) -> str:
        try:
            title = page.title().strip()
            fail = page.locator("#bpc_fail").first
            fail_text = fail.inner_text(timeout=500) if fail.count() else ""
            article_note = ""
            if article_diagnostic:
                article_note = (
                    f"chars={article_diagnostic.get('chars', 0)},"
                    f"words={article_diagnostic.get('words', 0)},"
                    f"declared={article_diagnostic.get('declared', 0)},"
                    "rawMarker="
                    f"{str(article_diagnostic.get('raw_marker', False)).lower()}"
                )
            return " · ".join(
                item
                for item in (
                    http_diagnostic,
                    title[:100],
                    fail_text[:160],
                    article_note,
                )
                if item
            )
        except Exception as exc:  # noqa: BLE001 采诊断信息本身不许抛在真失败前面
            log.debug("读取 BPC 页面诊断失败:%s", exc)
            return http_diagnostic

    @classmethod
    def _fetch_one(cls, context, request: FetchRequest) -> tuple[str, str]:
        cookies = cookies_from_header(request.cookie, request.site)
        if cookies:
            context.add_cookies(cookies)
        page = context.new_page()
        deadline = time.monotonic() + request.timeout_seconds
        diagnostic = ""
        challenge_announced = False
        last_body = ""
        stable_polls = 0
        try:
            response = page.goto(
                request.url,
                wait_until="domcontentloaded",
                timeout=request.timeout_seconds * 1000,
                referer="https://www.google.com/",
            )
            http_diagnostic = f"HTTP {response.status}" if response is not None else ""
            while time.monotonic() < deadline:
                if request.probe:
                    verdict = str(page.evaluate(request.probe) or "")
                    if verdict.startswith("READY\n"):
                        return verdict[6:], page.url
                    diagnostic = " · ".join(
                        item for item in (http_diagnostic, verdict[5:180]) if item
                    )
                    page.wait_for_timeout(1_000)
                    continue
                article_diagnostic: dict[str, object] = {}
                article = cls._article_html(
                    page,
                    request.min_chars,
                    request.min_words,
                    request.min_coverage,
                    request.selectors,
                    request.paragraph_selectors,
                    request.reject_patterns,
                    article_diagnostic,
                )
                if article:
                    html, final_url, body_text = article
                    stable_polls = stable_polls + 1 if body_text == last_body else 1
                    last_body = body_text
                    if stable_polls >= request.settle_polls:
                        return html, final_url
                diagnostic = cls._diagnostic(
                    page, http_diagnostic, article_diagnostic
                )
                # 「这个站在要人验证」是页面说的,不是站名说的。原来这里写着
                # `request.site == "bloomberg"`,于是路透社同样弹滑块却什么都不喊,
                # 一篇干等到超时(2026-08-07 站长截图 + 一轮 30.6 分钟)。
                if not challenge_announced and HUMAN_CHECK_RX.search(diagnostic):
                    challenge_announced = True
                    if cls._headless():
                        log.warning("%s 无头模式命中真人验证；本轮不会打开窗口，将按超时失败留档。", request.site)
                    else:
                        page.bring_to_front()
                        log.warning("%s 要求一次真人验证：请在弹出的浏览器窗口完成验证；"
                                    "通过后自动继续，状态只保存在本机专用 profile。", request.site)
                page.wait_for_timeout(1_000)
            raise BrowserBypassError(
                f"BPC 扩展运行后仍未恢复出完整 {request.site} 正文"
                f"(等待 {request.timeout_seconds} 秒;{diagnostic or '无页面诊断'})"
            )
        finally:
            page.close()

    def close(self) -> None:
        thread = self._thread
        if thread and thread.is_alive():
            self._requests.put(None)
            thread.join(timeout=10)


WORKER = BrowserWorker()
atexit.register(WORKER.close)


def _validate_public_target(url: str, site: str) -> None:
    if site not in SITE_DOMAINS or site_for_url(url) != site:
        raise BrowserBypassError("公开无头浏览器只允许读取已登记媒体的 HTTPS 页面")


def _public_context(playwright):
    """临时、无 profile、无扩展的公开站 context；不会镜像日常 Chrome Cookie。"""
    browser = playwright.chromium.launch(headless=True)
    context = browser.new_context(
        locale="en-US",
        viewport={"width": 1365, "height": 1000},
    )
    context.add_init_script(
        "Object.defineProperty(navigator, 'webdriver', {get: () => undefined});"
    )
    return browser, context


def fetch_public_page_headless(
    url: str,
    *,
    site: str,
    min_chars: int = 600,
    min_words: int = 0,
    min_coverage: float = 0.0,
    selectors: tuple[str, ...] = (),
    paragraph_selectors: tuple[str, ...] = (),
    reject_patterns: tuple[str, ...] = (),
    settle_polls: int = 1,
    timeout_seconds: int = 90,
) -> tuple[str, str]:
    """公开页面的纯无头兜底；不装 BPC，也不读取管理员浏览器资料。"""
    _validate_public_target(url, site)
    status = public_status()
    if not status["ok"]:
        raise BrowserBypassError(str(status["note"]))
    timeout_seconds = max(15, min(int(timeout_seconds), 180))
    deadline = time.monotonic() + timeout_seconds
    try:
        from playwright.sync_api import sync_playwright

        with sync_playwright() as playwright:
            browser, context = _public_context(playwright)
            page = context.new_page()
            last_body = ""
            stable_polls = 0
            diagnostic = ""
            try:
                response = page.goto(
                    url,
                    wait_until="domcontentloaded",
                    timeout=timeout_seconds * 1000,
                    referer="https://www.google.com/",
                )
                http = f"HTTP {response.status}" if response is not None else ""
                while time.monotonic() < deadline:
                    article_diagnostic: dict[str, object] = {}
                    article = BrowserWorker._article_html(
                        page,
                        max(100, int(min_chars)),
                        max(0, int(min_words)),
                        max(0.0, float(min_coverage)),
                        tuple(selectors),
                        tuple(paragraph_selectors),
                        tuple(reject_patterns),
                        article_diagnostic,
                    )
                    if article:
                        html, final_url, body_text = article
                        stable_polls = stable_polls + 1 if body_text == last_body else 1
                        last_body = body_text
                        if stable_polls >= max(1, int(settle_polls)):
                            return html, final_url
                    diagnostic = BrowserWorker._diagnostic(
                        page, http, article_diagnostic
                    )
                    page.wait_for_timeout(1_000)
                raise BrowserBypassError(
                    f"公开无头浏览器仍未读到完整 {site} 正文"
                    f"(等待 {timeout_seconds} 秒;{diagnostic or '无页面诊断'})"
                )
            finally:
                context.close()
                browser.close()
    except BrowserBypassError:
        raise
    except Exception as exc:  # noqa: BLE001 浏览器启动与页面异常统一保留原话
        raise BrowserBypassError(
            f"公开无头浏览器失败:{type(exc).__name__}: {exc}"
        ) from exc


def fetch_public_listing_headless(
    url: str,
    *,
    site: str,
    probe: str,
    timeout_seconds: int = 45,
) -> tuple[str, str]:
    """公开列表的纯无头通道；完成条件仍由共享 probe 自证。"""
    _validate_public_target(url, site)
    status = public_status()
    if not status["ok"]:
        raise BrowserBypassError(str(status["note"]))
    timeout_seconds = max(15, min(int(timeout_seconds), 180))
    deadline = time.monotonic() + timeout_seconds
    try:
        from playwright.sync_api import sync_playwright

        with sync_playwright() as playwright:
            browser, context = _public_context(playwright)
            page = context.new_page()
            diagnostic = ""
            try:
                response = page.goto(
                    url,
                    wait_until="domcontentloaded",
                    timeout=timeout_seconds * 1000,
                    referer="https://www.google.com/",
                )
                http = f"HTTP {response.status}" if response is not None else ""
                while time.monotonic() < deadline:
                    verdict = str(page.evaluate(probe) or "")
                    if verdict.startswith("READY\n"):
                        return verdict[6:], page.url
                    diagnostic = " · ".join(
                        item for item in (http, verdict[5:180]) if item
                    )
                    page.wait_for_timeout(1_000)
                raise BrowserBypassError(
                    f"公开无头浏览器列表未完成(等待 {timeout_seconds} 秒;"
                    f"{diagnostic or '无页面诊断'})"
                )
            finally:
                context.close()
                browser.close()
    except BrowserBypassError:
        raise
    except Exception as exc:  # noqa: BLE001 同正文通道，原样保留启动/页面错误
        raise BrowserBypassError(
            f"公开无头浏览器失败:{type(exc).__name__}: {exc}"
        ) from exc


def fetch_ft_page_bypassed(
    url: str,
    *,
    cookie: str = "",
    min_chars: int = 600,
    timeout_seconds: int | None = None,
) -> tuple[str, str]:
    timeout = timeout_seconds or int(os.getenv("FT_BYPASS_TIMEOUT_SECONDS", "75"))
    return WORKER.fetch(
        url,
        site="ft",
        cookie=cookie,
        min_chars=max(100, int(min_chars)),
        timeout_seconds=timeout,
    )


def fetch_bloomberg_page_isolated(
    url: str, *, min_chars: int = 500, timeout_seconds: int = 180
) -> tuple[str, str]:
    return WORKER.fetch(
        url,
        site="bloomberg",
        cookie="",
        min_chars=max(100, int(min_chars)),
        timeout_seconds=timeout_seconds,
    )


def fetch_listing_isolated(
    url: str,
    *,
    site: str,
    probe: str,
    timeout_seconds: int = 45,
) -> tuple[str, str]:
    """无头读取栏目/搜索页 —— 发现阶段的静默通道。

    2026-08-08 之前这条路根本不存在:发现一律走日常 Chrome,于是分栏只覆盖了
    取正文,而发现才是弹得最凶的一段(Bloomberg 11 个入口页、WSJ 9 个搜索词,
    每轮固定开这么多个可见标签)。
    """
    return WORKER.fetch_listing(
        url, site=site, probe=probe, timeout_seconds=timeout_seconds
    )


def fetch_paid_page_isolated(
    url: str,
    *,
    site: str,
    min_chars: int = 600,
    min_words: int = 0,
    min_coverage: float = 0.0,
    selectors: tuple[str, ...] = (),
    paragraph_selectors: tuple[str, ...] = (),
    reject_patterns: tuple[str, ...] = (),
    settle_polls: int = 1,
    timeout_seconds: int = 90,
) -> tuple[str, str]:
    """声明式付费站的无头通道;验收参数由调用方(该站声明)决定,这里不设默认宽松值。"""
    return WORKER.fetch(
        url,
        site=site,
        cookie="",
        min_chars=max(100, int(min_chars)),
        min_words=max(0, int(min_words)),
        min_coverage=max(0.0, float(min_coverage)),
        selectors=tuple(selectors),
        paragraph_selectors=tuple(paragraph_selectors),
        reject_patterns=tuple(reject_patterns),
        settle_polls=max(1, int(settle_polls)),
        timeout_seconds=timeout_seconds,
    )
