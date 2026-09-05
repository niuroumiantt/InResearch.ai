"""把抓到的清单渲染成静态 HTML(纯函数,不写盘、不出网)。

版式沿用 inews.today 的 Signal Desk 设计语言(深色控制台头 + 硬边网格 +
时间线),这样 FT 清单挂到 inews.today/rawarticle/ft 下面时不像外挂的第三方页。
样式落在同目录的 ``site.css``:一份文件被清单页、分析页和每一篇正文页共用,
双击本地文件和走服务器都能打开(相对路径)。

正文取失败时**照实写出服务端/浏览器的原话**,不用"暂无内容"顶掉 —— 兜底文案会
让一次真实的登录态失效看起来像一篇没正文的稿子。
"""
from __future__ import annotations

import hashlib
from html import escape
from typing import Any

from inews import keywords as kw
from inews import layout
from inews import quality as quality_module
from inews import runlog
from inews import stats as stats_module
from inews.textutil import parse_datetime

STYLESHEET_NAME = "site.css"


def _fingerprint(text: str) -> str:
    """样式表内容的短指纹。用途只有一个:让缓存在版式变了的时候失效。"""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:10]

# 与 inews.today 的 web/sd-ui-kit.css 同源(同一套 token 与硬边网格),
# 但这里是**独立一份**:inews 不依赖那个仓库存在,也不出网取样式。
STYLESHEET = """
:root {
  --paper: #f3f0e8; --surface: #fff; --panel: #ece9df; --console: #111719;
  --ink: #151c1f; --muted: #4d585b; --line: #c9ccc5; --line-strong: #aeb4ad;
  --acid: #d7ff35; --alert: #e5472e; --ok: #087a55; --link: #1769aa;
  /* 标题自己一个颜色:比正文深、带一点蓝,和英文原题(muted)、标签(线框)
     分成三层。不用 --link 那个蓝 —— 那个蓝在页面上代表「跳去站外」。 */
  --headline: #16324a;
  /* 分类色板:**颜色只编码主题域**,不编码大小、好坏、排名。
     八个槽是验证过的一套(色盲视角下相邻两色可分),第九个类别一律走中性灰
     —— 现生一个新颜色,就会有两个色在色盲视角下变成同一个。
     纸面偏暖,其中四个槽对比度不到 3:1,所以**每个色块旁边永远带名字和数字**;
     颜色是第二线索,不是唯一线索。 */
  --domain-1: #2a78d6; --domain-2: #eb6834; --domain-3: #1baf7a; --domain-4: #eda100;
  --domain-5: #e87ba4; --domain-6: #008300; --domain-7: #4a3aa7; --domain-8: #e34948;
  --domain-other: #8c9195;
  --sans: Arial, "PingFang SC", "Microsoft YaHei", sans-serif;
  --mono: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
}
* , *::before, *::after { box-sizing: border-box; }
/* `hidden` 属性只声明 display:none,而 .row 自己是 display:grid —— 后者赢,
   于是筛选把计数改了、行却一条不少地留在页面上(2026-08-22 站长报)。
   计数和列表说的不是同一件事,比两边都错更难查。 */
[hidden] { display: none !important; }
body {
  margin: 0; min-height: 100%; color: var(--ink); font-family: var(--sans);
  background: radial-gradient(circle at 80% 5%, #fff 0, transparent 24%), var(--paper);
}
a { color: inherit; }

/* ---- 控制台头:每一页都带,知道自己在哪一站、哪一页 ---- */
.console {
  position: sticky; top: 0; z-index: 10; display: flex; flex-wrap: wrap;
  align-items: center; gap: 14px; padding: 9px 30px;
  border-bottom: 3px solid var(--acid); background: var(--console); color: #f7f7f2;
  font: 700 10px/1.2 var(--mono); letter-spacing: .06em;
}
.console .brand::before {
  content: ""; display: inline-block; width: 7px; height: 7px; margin-right: 8px;
  border-radius: 50%; background: var(--alert);
}
.console .tag { margin-left: 7px; padding: 3px 5px; background: var(--acid); color: #111; font-size: 8px; }
.tabs { display: flex; }
.tabs a { padding: 8px 12px; border-left: 1px solid #354042; color: #c3ccca; text-decoration: none; }
.tabs a:last-child { border-right: 1px solid #354042; }
.tabs a[aria-current="page"], .tabs a:hover { background: var(--acid); color: #111; }
/* 两层导航:上层选库、下层选页。上层往左推、下层贴右,**两行在视觉上必须分得开**
   —— 9-03 之前它们平铺成一行,「清单」(本库的页)和「FT.COM」(另一个库)
   长得一模一样,点之前不知道会去哪。 */
.tabs--sites { margin-left: auto; }
.tabs--sites a[aria-current="true"] { background: #2b3436; color: var(--acid); cursor: default; }
.tabs--pages { margin-left: 14px; }
.tabs--pages a { font-weight: 800; }

.frame { max-width: 1180px; margin: auto; padding: 22px 30px 60px; }
.frame--read { max-width: 860px; }

/* ---- 报头 ---- */
.kicker {
  display: flex; justify-content: space-between; gap: 12px; flex-wrap: wrap;
  padding-bottom: 12px; border-bottom: 1px solid var(--ink);
  font: 700 11px/1.2 var(--mono); letter-spacing: .16em;
}
.hero { display: grid; grid-template-columns: 1fr 300px; gap: 38px; align-items: end; padding: 30px 0 24px; }
.hero h1 { margin: 0; font-size: clamp(34px, 5vw, 62px); font-weight: 900; line-height: 1.12; letter-spacing: -.03em; }
.hero .lede { max-width: 660px; margin: 16px 0 0; color: var(--muted); font-size: 13.5px; line-height: 1.6; }
.clock { display: flex; flex-direction: column; padding: 14px 0 14px 22px; border-left: 1px solid var(--ink); }
.clock span { color: var(--muted); font: 700 9px/1.5 var(--mono); letter-spacing: .1em; }
.clock strong { margin: 6px 0 12px; font: 800 15px/1.3 var(--mono); }

/* ---- 顶部总览:三条并排的带 ---- */
/* **一套格子管到底**:三条带用同一个 .band__grid,每格结构也一样(值 / 标签 /
   图形)。8-24 站长指的「都没有对齐」,根子是每块自己排自己的 —— 值的字号、
   标签的位置、有没有图形,各写各的,于是列与列之间怎么也对不齐。 */
.band { margin: 0 0 12px; border: 1px solid var(--line-strong); background: var(--surface); }
.band__head { display: flex; justify-content: space-between; align-items: baseline; gap: 10px;
  padding: 8px 12px; border-bottom: 1px solid var(--line-strong); background: var(--panel);
  font: 800 10px var(--mono); letter-spacing: .12em; }
.band__head em { color: var(--muted); font-style: normal; font-weight: 700;
  letter-spacing: .04em; text-align: right; overflow-wrap: anywhere; }
.band__head em.bad { color: var(--alert); }
.band__grid { display: grid; }
.band__grid--6 { grid-template-columns: repeat(6, 1fr); }
.band__grid--1 { grid-template-columns: 1fr; }
/* 每格自己是一列网格:值、标签、图形各占一行,**行高固定**,所以横着看每一行
   都在同一条基线上 —— 有没有图形都一样。 */
.cell { display: grid; grid-template-rows: 26px 14px 10px; gap: 5px; align-content: start;
  padding: 12px 14px; border-right: 1px solid var(--line); }
.cell:last-child { border-right: 0; }
.cell strong { font: 900 22px/26px var(--mono); letter-spacing: -.02em;
  font-size: clamp(13px, 1.35vw, 22px);
  overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.cell strong.bad { color: var(--alert); }
.cell span { color: var(--muted); font: 700 9px/14px var(--mono); letter-spacing: .08em; }
.cell__art { align-self: center; }
/* 覆盖条:取到 / 失败 / 还没取。空段不画 —— 一条 0 宽的色块只会变成噪点。 */
.cover { display: flex; height: 6px; background: var(--line); overflow: hidden; }
.cover i { height: 100%; }
.cover--ok { background: var(--ok); }
.cover--bad { background: var(--alert); }
.cover--rest { background: var(--line-strong); }
/* 名字别和 dashboard 那条 .axis 撞 —— 撞了就是「样式看起来随机失效」。 */
.spanline { display: flex; align-items: center; gap: 6px;
  color: var(--muted); font: 700 8px var(--mono); letter-spacing: .04em; }
.spanline i { flex: 1; height: 1px; background: var(--line-strong); }

/* ---- 最近几轮 + 抓一轮按钮 ---- */
.cadence__body { display: grid; grid-template-columns: 1fr 296px; }
.cadence ol { margin: 0; padding: 10px 14px; list-style: none; }
/* 五行共用一套列宽:时间、条、新增、命中 各自成列,所以数字是**竖着对齐**的。 */
.cadence li { display: grid; grid-template-columns: 152px 1fr 64px 72px;
  align-items: center; gap: 10px; padding: 5px 0; border-top: 1px solid var(--line);
  font: 700 11px/1.4 var(--mono); }
.cadence li:first-child { border-top: 0; }
.cadence li b { font-weight: 800; }
.cadence li span { color: var(--muted); }
.cadence li em { grid-column: 1 / -1; color: var(--alert); font-style: normal;
  font-size: 10px; overflow-wrap: anywhere; }
.cadence li.bad b, .cadence li.bad span { color: var(--alert); }
.runbar { display: block; height: 8px; background: var(--line); }
.runbar i { display: block; height: 100%; background: var(--ink); }
.cadence li.bad .runbar i { background: var(--alert); }
.cadence__run { display: flex; flex-direction: column; justify-content: center; gap: 9px;
  padding: 13px 14px; border-left: 1px solid var(--line-strong); background: var(--panel); }
.cadence__run button { padding: 11px 12px; border: 0; background: var(--ink); color: var(--acid);
  font: 800 12px var(--mono); letter-spacing: .06em; cursor: pointer; }
.cadence__run button:hover { background: #000; }
.cadence__run button.ok { background: var(--ok); color: #fff; }
.cadence__run button.warn { background: var(--alert); color: #fff; }
.cadence__run p { margin: 0; color: var(--muted); font: 600 10px/1.7 var(--mono);
  overflow-wrap: anywhere; }
.cadence__run code { color: var(--ink); font: 700 10px var(--mono); }

/* ---- 筛选条 ---- */
.controls { display: grid; grid-template-columns: repeat(auto-fit, minmax(150px, 1fr)); gap: 8px; padding: 9px; background: var(--ink); }
.controls input[type=search] { min-width: 0; padding: 9px 11px; border: 0; background: #fff; color: #111; font: 600 12px var(--sans); }
.controls label { display: flex; align-items: center; gap: 6px; padding: 0 4px; color: #d8ded9;
  font: 700 9px var(--mono); letter-spacing: .06em; }
.controls input[type=checkbox] { width: 13px; height: 13px; accent-color: var(--acid); }
/* 去主站那一条:同一条 tab 栏里,但用一条竖线分开「那边」和「这边」——
   两个站是一个项目,不是同一份产出。 */
.tabs .tabs__home { border-right: 1px solid #3a4548; margin-right: 4px; padding-right: 12px; }
.tabs .tabs__home::before { content: "◀ "; opacity: .6; }
.tallybar { display: flex; flex-wrap: wrap; align-items: center; justify-content: space-between;
  gap: 10px; padding-top: 10px; }
.pager { display: flex; align-items: center; gap: 8px;
  color: var(--muted); font: 700 10px var(--mono); letter-spacing: .06em; }
.pager select { padding: 4px 6px; border: 1px solid var(--line-strong); background: var(--surface);
  color: var(--ink); font: 700 11px var(--mono); }
.pager__info { min-width: 132px; color: var(--ink); }
.pager__nav { display: flex; gap: 6px; }
.pager button { padding: 5px 10px; border: 1px solid var(--line-strong); background: var(--surface);
  color: var(--ink); font: 700 10px var(--mono); letter-spacing: .06em; cursor: pointer; }
.pager button:hover:not(:disabled) { background: var(--ink); color: var(--acid); }
/* 到头了就是到头了:按钮变灰,不做成「点了没反应」。 */
.pager button:disabled { color: var(--line-strong); cursor: default; }
.tally { padding: 0; color: var(--muted); font: 700 10px var(--mono); letter-spacing: .1em; }
.tally b { color: var(--ink); }

/* ---- 抓取规则:这一页是怎么来的,写在页面自己身上 ---- */
.rules { margin-top: 14px; border: 1px solid var(--line-strong); background: var(--surface); padding: 10px 14px; }
.rules__head { font: 800 10px var(--mono); letter-spacing: .14em; color: var(--muted); }
.rules ul { margin: 6px 0 0; padding-left: 18px; }
.rules li { margin: 3px 0; font-size: 12px; line-height: 1.6; }

/* ---- 时间线 ---- */
.stream { margin-top: 18px; border-top: 4px solid var(--ink); }
.stream__head { display: flex; justify-content: space-between; padding: 8px 0; border-bottom: 1px solid var(--ink);
  font: 800 10px var(--mono); letter-spacing: .14em; }
.daysep { margin: 22px 0 0; padding: 7px 0; border-bottom: 1px solid var(--ink);
  font: 800 10px var(--mono); letter-spacing: .16em; }
.row { display: grid; grid-template-columns: 120px 1fr; gap: 14px; padding: 11px 0; border-bottom: 1px solid var(--line); }
.row .when { display: block; position: relative; padding-left: 18px; color: #354044; font: 700 11px/1.5 var(--mono); }
.row .when span { display: block; color: var(--muted); font-size: 8.5px; letter-spacing: .08em; }
.row .when::before { content: ""; position: absolute; left: 0; top: 4px; z-index: 1; width: 9px; height: 9px;
  border: 2px solid var(--ink); border-radius: 50%; background: var(--acid); }
.row .when::after { content: ""; position: absolute; left: 4px; top: 15px; bottom: -14px; width: 1px; background: #aeb3ad; }
.row:last-child .when::after { display: none; }
/* 标题那一行:标题在左,标签和来源被推到右边。标签换行时靠右对齐,
   不会把标题挤成两栏。 */
.titlerow { display: flex; flex-wrap: wrap; align-items: baseline; gap: 6px 12px; }
.titlerow .meta { margin: 0 0 0 auto; }
/* **标题自己一个颜色。** 和英文原题、标签分层:一眼看得出哪一行是标题。 */
.headline { color: var(--headline); font-size: 16px; font-weight: 760; line-height: 1.3;
  text-decoration: none; flex: 1 1 340px; min-width: 0; }
.row .story a.headline { font-size: 16px; font-weight: 760; line-height: 1.3; text-decoration: none; }
.row .story .headline--gone { display: block; color: var(--muted); font-size: 16px;
  font-weight: 760; line-height: 1.25; }
.row .story a.headline:hover { text-decoration: underline; text-decoration-color: #a9ce00; text-decoration-thickness: 3px; }
/* 英文原题:译文之下、标签之上。小而不藏 —— 核对时要看得见站方给的那一串。 */
.row .original { margin-top: 3px; color: var(--muted); font-size: 12px; line-height: 1.4; }
.row .meta { display: flex; flex-wrap: wrap; gap: 6px; align-items: center; }

.kw { display: inline-block; padding: 2px 7px; border: 1px solid var(--line-strong); background: var(--surface);
  font: 700 9px var(--mono); letter-spacing: .04em; white-space: nowrap; }
.badge { display: inline-block; padding: 2px 7px; border-radius: 999px; font: 800 9px var(--mono); white-space: nowrap; }
.score { display: inline-block; margin-left: 6px; padding: 1px 8px; border-radius: 999px;
  background: var(--headline); color: #a9ce00; font: 800 11px var(--mono); vertical-align: 2px; }
.scorecard { margin: 14px 0 18px; padding: 10px 14px; border: 1px solid var(--line-strong); background: var(--surface); }
.scorecard > b { margin-right: 10px; }
.scorecard .dims { margin: 8px 0 0; }
.scorecard .dim { display: inline-block; margin-right: 12px; color: var(--muted); font-size: 12px; }
.scorecard p { margin: 8px 0 0; font-size: 13px; line-height: 1.6; }
.scorecard--failed p { color: #a82016; }
.badge--alert { background: #fee8e4; color: #a82016; }
.badge--muted { background: #edf0f4; color: #555f70; }
.src { color: var(--link); font: 800 9px var(--mono); text-decoration: none; }
.src:hover { text-decoration: underline; }

/* ---- 本轮记录:失败在外面,常规的折起来 ---- */
.log { margin: 16px 0 4px; border: 1px solid var(--line-strong); background: var(--surface); }
.log__head { display: flex; justify-content: space-between; gap: 8px; padding: 8px 11px;
  border-bottom: 1px solid var(--line-strong); background: var(--panel);
  font: 800 10px var(--mono); letter-spacing: .12em; }
.log p { margin: 0 0 4px; overflow-wrap: anywhere; }
.log p:last-child { margin-bottom: 0; }
.log__bad { padding: 10px 12px; border-left: 3px solid var(--alert); background: #fee8e4;
  color: #7d1a12; font: 600 11.5px/1.6 var(--mono); }
.log summary { padding: 8px 12px; color: var(--muted); cursor: pointer;
  font: 800 10px var(--mono); letter-spacing: .1em; }
.log summary:hover { color: var(--ink); }
.log__all { max-height: 320px; overflow: auto; padding: 0 12px 12px;
  color: var(--muted); font: 600 11.5px/1.65 var(--mono); }

/* ---- 正文页 ---- */
.article h1 { margin: 26px 0 10px; font-size: clamp(26px, 3.4vw, 40px); font-weight: 900; line-height: 1.18; letter-spacing: -.02em; }
.article .byline { display: flex; flex-wrap: wrap; gap: 10px; align-items: center; padding-bottom: 14px;
  border-bottom: 1px solid var(--ink); color: var(--muted); font: 700 10px var(--mono); letter-spacing: .08em; }
.article .tags { display: flex; flex-wrap: wrap; gap: 6px; margin: 14px 0 22px; }
.article .body { font-size: 17px; line-height: 1.78; }
.article .body p { margin: 0 0 1.15em; }
.back { display: inline-block; margin: 22px 0 0; color: var(--link); font: 800 10px var(--mono);
  letter-spacing: .08em; text-decoration: none; }
.back:hover { text-decoration: underline; }
.failed { padding: 14px 16px; border: 1px solid var(--alert); border-left-width: 4px; background: #fee8e4;
  color: #7d1a12; font-size: 13.5px; line-height: 1.6; }
.failed b { display: block; margin-bottom: 4px; font: 800 10px var(--mono); letter-spacing: .1em; }

/* ---- 分析页表格 ---- */
h2 { margin: 30px 0 10px; font: 800 11px var(--mono); letter-spacing: .16em; text-transform: uppercase; }
table { width: 100%; border-collapse: collapse; font-size: 12.5px; }
th, td { padding: 6px 9px; border-bottom: 1px solid var(--line); text-align: left; }
td.num, th.num { white-space: nowrap; }
th { border-bottom: 1px solid var(--ink); color: var(--muted); font: 800 9px var(--mono); letter-spacing: .1em; }
td.num, th.num { text-align: right; font-family: var(--mono); }
tbody tr:hover { background: var(--surface); }
.bar { display: block; height: 11px; border: 1px solid var(--line); background: var(--panel); }
.bar > i { display: block; height: 100%; background: var(--ink); }


/* ---- 后台 dashboard ---- */
/* 12 栏网格:图占宽的,表占窄的。一列到底会让每张牌都拉成一条长条,
   信息密度还不如把它们并排放。 */
.board { display: grid; grid-template-columns: repeat(12, 1fr); gap: 14px; align-items: start; }
.card { border: 1px solid var(--line-strong); background: var(--surface); }
.card--3 { grid-column: span 3; } .card--4 { grid-column: span 4; }
.card--5 { grid-column: span 5; } .card--6 { grid-column: span 6; }
.card--7 { grid-column: span 7; }
.card--8 { grid-column: span 8; } .card--12 { grid-column: span 12; }
.card > details > summary { padding: 8px 11px; border-bottom: 1px solid var(--line-strong);
  background: var(--panel); cursor: pointer; font: 800 10px var(--mono); letter-spacing: .12em; }
.card > details[open] > summary { border-bottom: 1px solid var(--line-strong); }
.dot { display: inline-block; width: 8px; height: 8px; margin-right: 6px;
  border-radius: 2px; vertical-align: baseline; flex: none; }
.legend { display: flex; flex-wrap: wrap; gap: 4px 14px; margin-top: 10px;
  padding-top: 9px; border-top: 1px solid var(--line);
  color: var(--muted); font: 700 9.5px var(--mono); letter-spacing: .04em; }
.legend__key { display: flex; align-items: center; }
/* 小倍数:八张图共用一个纵轴上限,否则一条 2 篇的线和一条 40 篇的线一样高。 */
.minis { display: grid; grid-template-columns: repeat(4, 1fr); gap: 12px; }
.mini__head { display: flex; align-items: center; gap: 2px; margin-bottom: 5px;
  font: 700 9.5px var(--mono); letter-spacing: .04em; }
.mini__head span { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.mini__head b { margin-left: auto; font: 800 11px var(--mono); }
.spark--mini { height: 30px; }
/* 极性:涨一色、跌一色、零居中。不是渐变 —— 那会把方向变成大小。 */
.delta { width: 40%; }
.delta__rail { display: flex; justify-content: center; height: 10px;
  background: linear-gradient(to right, transparent calc(50% - 1px),
    var(--line-strong) calc(50% - 1px), var(--line-strong) calc(50% + 1px),
    transparent calc(50% + 1px)); }
.delta__bar { height: 100%; }
.delta__bar--up { margin-left: 50%; background: var(--domain-2); }
.delta__bar--down { margin-right: 50%; background: var(--domain-1); }
.delta__bar--flat { width: 0 !important; }
.delta__n--up { color: #b8480f; } .delta__n--down { color: #1c5fa8; }
.delta__n--flat { color: var(--muted); }
/* 关键词那张表有四十多行:给它一个自己的滚动框,而不是把整页拉长两屏。 */
.scroll { max-height: 320px; overflow: auto; }
.scroll table { font-size: 12px; }
.table-scroll { overflow-x: auto; }
.table-scroll table { min-width: 720px; }
.kpis { display: grid; grid-template-columns: repeat(8, 1fr); margin: 16px 0 18px;
  border: 1px solid var(--line-strong); background: var(--panel); }
.kpis .cell { grid-template-rows: 26px 14px; }
/* 堆叠条:三个数放成一条,比三句话快;数字仍然写在图例里,不靠估。 */
.stack { display: flex; height: 14px; border: 1px solid var(--line-strong); background: var(--panel); }
.stack__seg { display: block; height: 100%; }
.stack__seg--ok { background: var(--ok); }
.stack__seg--idle { background: var(--line-strong); }
.stack__seg--bad { background: var(--alert); }
.stack__legend { display: flex; flex-wrap: wrap; gap: 12px; margin: 8px 0 14px;
  color: var(--muted); font: 700 10px var(--mono); letter-spacing: .06em; }
.stack__key { display: flex; align-items: center; gap: 5px; }
.stack__key i { width: 9px; height: 9px; }
.stack__key b { color: var(--ink); }
/* **卡头一律同高、卡身一律同边距。** 8-24 站长指的「都没有对齐」,一半来自
   这里:标题短的那张卡头矮一截,并排放就成了台阶。固定行高 + 单行省略。 */
.card__head { display: flex; justify-content: space-between; align-items: baseline; gap: 8px;
  min-height: 32px; padding: 9px 12px;
  border-bottom: 1px solid var(--line-strong); background: var(--panel);
  font: 800 10px/14px var(--mono); letter-spacing: .12em; }
.card__head span:last-child { flex: none; max-width: 55%; color: var(--muted);
  font-weight: 700; letter-spacing: .04em; text-align: right;
  overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.card__body { padding: 12px; }
/* 架构图:线和字都跟着主题走,别在 SVG 里写死颜色(深色下会变成隐形的)。 */
.arch { display: block; width: 100%; height: auto; margin-bottom: 12px; }
.arch .node { fill: var(--panel); stroke: var(--line-strong); }
.arch .node__t { font: 800 12px var(--mono); fill: var(--ink); }
.arch .node__w { font: 700 9px var(--mono); fill: var(--muted); letter-spacing: .04em; }
.arch .node__n { font: 600 9px var(--mono); fill: var(--muted); }
.arch .edge { fill: none; stroke: var(--line-strong); stroke-width: 1.5; }
.arch .edge__h { fill: var(--line-strong); }
.status { display: flex; align-items: center; gap: 10px; padding: 12px; }
.status .lamp { width: 12px; height: 12px; border: 2px solid var(--ink); border-radius: 50%; flex: none; }
.status .lamp--ok { background: var(--acid); }
.status .lamp--bad { background: var(--alert); }
.status .lamp--idle { background: var(--panel); }
.status b { display: block; font: 800 13px var(--mono); }
.status span { color: var(--muted); font-size: 11px; line-height: 1.5; }
.kv { display: grid; grid-template-columns: 1fr auto; gap: 5px 10px; font-size: 12px; }
.kv dt { color: var(--muted); }
.kv dd { margin: 0; font: 700 12px var(--mono); text-align: right; }
/* 一行一条的说明:左栏定宽,所以每条的正文左边是**同一条竖线**。 */
.kv--wide { grid-template-columns: 116px 1fr; gap: 8px 12px; align-items: start; }
.kv--wide dd { font: 600 11px/1.65 var(--sans); text-align: left; color: var(--muted); }
.kv--wide dt { font: 800 10px/1.65 var(--mono); letter-spacing: .06em; color: var(--ink); }
.spark { display: flex; align-items: flex-end; gap: 2px; height: 46px; }
.spark i { flex: 1; min-width: 2px; background: var(--ink); }
.spark i.zero { background: var(--line); height: 2px !important; }
.spark i.bad { background: var(--alert); }
.axis { display: flex; justify-content: space-between; margin-top: 5px; color: var(--muted);
  font: 700 8.5px var(--mono); letter-spacing: .06em; }
/* table-layout:fixed:格子平分剩下的宽度。默认布局会让格子挤在右边,
   左边留出一大片空白 —— 热力图的信息量全在那片格子里。 */
.heat { width: 100%; table-layout: fixed; border-collapse: collapse; font-size: 11px; }
.heat td.word { width: 30%; overflow: hidden; text-overflow: ellipsis; }
.heat th { padding: 3px 2px; border: 0; font: 700 8px var(--mono); letter-spacing: 0; text-align: center; }
.heat td { padding: 0; border: 0; }
.heat td.word { padding-right: 8px; white-space: nowrap; font: 600 11px var(--sans); text-align: left; }
.heat i { display: block; height: 15px; margin: 1px; background: var(--ink); }
.rows { width: 100%; border-collapse: collapse; font-size: 12.5px; }
.rows th { position: sticky; top: 38px; background: var(--paper); }
.rows td { vertical-align: top; }
.rows td.mark { width: 22px; font: 800 13px var(--mono); text-align: center; }
.rows td.mark.ok { color: var(--ok); }
.rows td.mark.bad { color: var(--alert); }
.rows td.mark.idle { color: var(--muted); }
.rows td.day { width: 96px; color: var(--muted); font: 700 10px var(--mono); white-space: nowrap; }
.rows .why { display: block; margin-top: 3px; color: #a82016; font-size: 11px; }
.rows .words { display: block; margin-top: 3px; color: var(--muted); font: 600 10px var(--mono); }
@media (max-width: 1080px) {
  .kpis { grid-template-columns: repeat(4, 1fr); }
  .kpis .cell:nth-child(4n) { border-right: 0; }
  .kpis .cell:nth-child(n + 5) { border-top: 1px solid var(--line-strong); }
  .card--3, .card--4, .card--6, .card--8 { grid-column: span 12; }
  .minis { grid-template-columns: repeat(2, 1fr); }
}

.empty { padding: 44px 0; color: var(--muted); text-align: center; font: 700 11px var(--mono); letter-spacing: .1em; }

@media (max-width: 800px) {
  .console { padding: 9px 14px; }
  .frame { padding: 16px 14px 40px; }
  .hero { grid-template-columns: 1fr; gap: 18px; }
  .clock { padding: 14px 0 0; border-top: 1px solid var(--ink); border-left: 0; }
  .band__grid--6 { grid-template-columns: repeat(2, 1fr); }
  .cell { border-bottom: 1px solid var(--line); }
  .cadence__body { grid-template-columns: 1fr; }
  .cadence li { grid-template-columns: 1fr 1fr; }
  .cadence__run { border-left: 0; border-top: 1px solid var(--line-strong); }
  .metric:nth-child(2n) { border-right: 0; }
  .metric:nth-child(n + 3) { border-top: 1px solid var(--line-strong); }
  .row { grid-template-columns: 1fr; gap: 6px 10px; }
  .row .when::after { display: none; }
  .row .story { padding-left: 18px; }
}
"""


STYLESHEET_FINGERPRINT = _fingerprint(STYLESHEET)

# 筛选全在浏览器本地做:清单是静态文件,双击就能看,不需要跑服务。
_FILTER_JS = """
const q = document.getElementById('q');
const mentions = document.getElementById('mentions');
const lowscores = document.getElementById('lowscores');
const secondary = document.getElementById('secondary');
const boxes = [...document.querySelectorAll('.controls input[type=checkbox]')]
  .filter(b => b !== mentions && b !== lowscores && b !== secondary);
const items = [...document.querySelectorAll('.row')];
const shown = document.getElementById('shown');
const sizeSel = document.getElementById('pagesize');
const info = document.getElementById('pageinfo');
const prev = document.getElementById('prev');
const next = document.getElementById('next');
// 每页多少条记在本地:这是个人偏好,不是内容 —— 换一次就该一直是它。
// 存不进去(隐私窗口、禁了站点数据)就用默认值,不为此报错。
const KEY = 'inews:pagesize';
try {
  const saved = localStorage.getItem(KEY);
  if (saved !== null && [...sizeSel.options].some(o => o.value === saved)) sizeSel.value = saved;
} catch (_) {}
let page = 1;

function apply() {
  const text = (q.value || '').trim().toLowerCase();
  const groups = boxes.filter(b => b.checked).map(b => b.value);
  // 先筛,再分页。**分页只作用在筛完剩下的那些上** —— 反过来的话,
  // 「第 2 页」会变成「原始第 51-100 条里筛剩的那几条」,那不是任何人想要的。
  const hits = [];
  for (const li of items) {
    const hitText = !text || li.dataset.search.includes(text);
    const hitGroup = !groups.length
      || groups.some(g => li.dataset.groups.split('|').includes(g));
    const hitMention = !li.dataset.mention || mentions.checked;
    const hitLow = !li.dataset.low || lowscores.checked;
    const hitQuality = !li.dataset.quality || secondary.checked;
    if (hitText && hitGroup && hitMention && hitLow && hitQuality) hits.push(li); else li.hidden = true;
  }
  const size = parseInt(sizeSel.value, 10) || 0;
  const pages = size ? Math.max(1, Math.ceil(hits.length / size)) : 1;
  if (page > pages) page = pages;
  if (page < 1) page = 1;
  const from = size ? (page - 1) * size : 0;
  const to = size ? from + size : hits.length;
  hits.forEach((li, i) => { li.hidden = i < from || i >= to; });
  const visible = Math.min(to, hits.length) - from;
  shown.textContent = hits.length;
  info.textContent = size
    ? `第 ${page} / ${pages} 页 · 本页 ${Math.max(0, visible)} 篇`
    : `全部 ${hits.length} 篇`;
  prev.disabled = page <= 1;
  next.disabled = page >= pages;
  // 整天都被筛掉(或翻到别页)时,那条日期分隔线也跟着藏起来 ——
  // 否则会剩下一排空标题。
  for (const sep of document.querySelectorAll('.daysep')) {
    let any = false;
    for (let el = sep.nextElementSibling; el && !el.classList.contains('daysep'); el = el.nextElementSibling) {
      if (el.classList.contains('row') && !el.hidden) { any = true; break; }
    }
    sep.hidden = !any;
  }
}

function toTop() {
  // 翻页之后跳回列表顶上:停在原来的滚动位置会让人以为「什么都没发生」。
  const head = document.querySelector('.stream');
  if (head) head.scrollIntoView({ block: 'start' });
}

q.addEventListener('input', () => { page = 1; apply(); });
boxes.forEach(b => b.addEventListener('change', () => { page = 1; apply(); }));
mentions.addEventListener('change', () => { page = 1; apply(); });
lowscores.addEventListener('change', () => { page = 1; apply(); });
secondary.addEventListener('change', () => { page = 1; apply(); });
sizeSel.addEventListener('change', () => {
  page = 1;
  try { localStorage.setItem(KEY, sizeSel.value); } catch (_) {}
  apply();
});
prev.addEventListener('click', () => { page--; apply(); toTop(); });
next.addEventListener('click', () => { page++; apply(); toTop(); });
apply();
"""

_RUN_JS = """
// 两个按钮同一套接线:各自带着自己的 endpoint 和兜底命令(见 _actions_for)。
for (const btn of document.querySelectorAll('#run, #repair')) {
  const label = btn.textContent;
  const endpoint = btn.dataset.endpoint;
  const say = (text, cls) => {
    btn.textContent = text;
    btn.className = cls || '';
    setTimeout(() => { btn.textContent = label; btn.className = ''; }, 8000);
  };
  btn.addEventListener('click', async () => {
    btn.textContent = '正在叫本机跑…';
    try {
      const res = await fetch(endpoint, { method: 'POST', mode: 'cors' });
      const data = await res.json();
      say(data.reason, data.started ? 'ok' : 'warn');
    } catch (err) {
      // **监听没开的时候不许装作按成功了。** 退回到把命令交到手上,
      // 并且把浏览器的原话留着 —— 兜底文案顶掉真实错误是这个仓库反复出事的地方。
      try { await navigator.clipboard.writeText(btn.dataset.cmd); } catch (_) {}
      say('本机监听没开(' + err + ')。命令已复制,去终端粘贴', 'warn');
    }
  });
}
"""

# 「关键词分析」并进了后台:两张页本来就是同一件事(都是这批稿子的结构性事实),
# 分成两页只是让人在两个标签之间来回找同一个答案。
# **一个 repo,一个项目。** 主站的时间线和各库的清单/后台并排成一条 tab 栏,
# 在哪一页看到的都是同一条。站外与姊妹库用绝对地址:这份产出挂在
# /rawarticle/<站>/ 下,相对路径爬不回站点根。/rawarticle/* 整个在 infra 的
# 同一个 forward_auth 后面,库与库之间点过去不用再登一次;时间线的登录
# 自 8-21 起归 inews 应用自己管,和这里无关。
_HOME_URL = "https://inews.today/"
_DASHBOARD_URL = f"{_HOME_URL}rawarticle/dashboard/"
# 下层导航:这个库里的页面。加页面只在这里加一行,两层导航各管各的。
_PAGES = (
    ("index.html", "清单"),
    (_DASHBOARD_URL, "统一后台"),
)


def _is_external(href: str) -> bool:
    return href.startswith("http")


def _library_tabs(site_key: str) -> tuple[tuple[str, str, bool], ...]:
    """上层导航:主站 + 每一个库,当前这个标出来。

    迟一步导入:声明的依赖流向里 render 与 sites 平级,顶层互 import 会把
    「渲染层只认词汇表」这条线搅浑;这里只在画导航时看一眼注册表拿 KEY/LABEL。
    """
    from inews import sites

    return ((_HOME_URL, "时间线 · 主站", False),) + tuple(
        (f"{_HOME_URL}rawarticle/{site.KEY}/index.html", site.LABEL,
         site.KEY == site_key)
        for site in sites.REGISTRY.values()
    ) + ((_DASHBOARD_URL, "统一后台", site_key == "all"),)


def _console(active: str, base: str = "", site_label: str = "FT.COM",
             site_key: str = "ft") -> str:
    """页眉分两层。

    9-03 站长:「目录不清晰无逻辑,要能体现到每个单独的页面,也要有跨页面。」
    病根是上一版把两种东西平铺成一行:「清单」是本库的一页,「FT.COM」是**另一个
    库**,长得却一模一样,点之前不知道会去哪。现在分开:
      上层 = 我在哪个库(主站 / 各库),当前的标 aria-current="true";
      下层 = 这个库里的哪一页(清单 / 后台),当前的标 aria-current="page"。
    姊妹库永远是绝对地址(产出挂在 /rawarticle/<站>/ 下,相对路径爬不回站点根),
    本库两页永远是相对地址(正文页深两层,靠 base 往上走)。
    """
    sites_row = "".join(
        f'<a href="{escape(href)}"'
        + (' aria-current="true"' if here else "")
        + (' class="tabs__home"' if href == _HOME_URL else "")
        + f">{escape(label)}</a>"
        for href, label, here in _library_tabs(site_key)
    )
    pages_row = "" if site_key == "all" else "".join(
        f'<a href="{escape(href if _is_external(href) else base + href)}"'
        + (' aria-current="page"' if href == active else "")
        + f">{escape(label)}</a>"
        for href, label in _PAGES
    )
    return (
        '<header class="console"><span class="brand">INEWS.TODAY'
        f'<span class="tag">{escape(site_label)}</span></span>'
        f'<nav class="tabs tabs--sites" aria-label="库">{sites_row}</nav>'
        + (f'<nav class="tabs tabs--pages" aria-label="本库页面">{pages_row}</nav>'
           if pages_row else "")
        + "</header>"
    )


def _page(
    title: str,
    body: str,
    *,
    script: str = "",
    active: str = "",
    read: bool = False,
    base: str = "",
    site_label: str = "FT.COM",
    site_key: str = "ft",
) -> str:
    """``base`` 是这一页回到站点根的相对前缀。

    正文页在 ``p/<年月>/`` 里,离根两层 —— 样式表、导航和回链都得跟着往上走。
    写死成同目录的话,双击本地文件时正文页会变成一张没有样式的白纸。
    """
    tail = f"<script>{script}</script>" if script else ""
    frame = "frame frame--read" if read else "frame"
    return (
        "<!doctype html>\n"
        '<html lang="zh-CN"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width, initial-scale=1">'
        f"<title>{escape(title)}</title>"
        # **带内容指纹**:路径永远不变的话,浏览器和 Caddy 会一直用缓存里那份 ——
        # 2026-08-22 后台改完发布上去,页面是新的、样式是旧的,看起来像代码没生效。
        f'<link rel="stylesheet" '
        f'href="{escape(base + STYLESHEET_NAME)}?v={STYLESHEET_FINGERPRINT}"></head>'
        f'<body>{_console(active, base, site_label, site_key)}<main class="{frame}">{body}</main>{tail}</body></html>\n'
    )


def article_filename(row: dict[str, Any]) -> str:
    """清单页到某篇正文页的相对路径(``p/<年月>/<uuid>.html``)。"""
    return layout.page_relpath(row["article_id"], row.get("published_at", ""))


def _title(row: dict[str, Any]) -> str:
    """显示用的标题:有译文用译文,没有就是英文原题。

    **不拿英文冒充译文**,也不给「(未翻译)」这种占位 —— 原题本身就是事实。
    """
    return str(row.get("title_zh") or "").strip() or str(row.get("title_en") or "")


def _original_line(row: dict[str, Any]) -> str:
    """译文下面那行英文原题。翻译过的稿子要能**逐字**核对站方给的那一串。"""
    if not str(row.get("title_zh") or "").strip():
        return ""
    return f'<div class="original">{escape(str(row.get("title_en") or ""))}</div>'


# 低分折叠线(9-01 站长:「让我们低分折叠吧」,前一句是「我要精不要多」)。
# 60 来自当天页面上的实际分布:清晰的垃圾都 ≤51,正稿都 ≥74,60 落在沟里。
# **藏不是删**:台账、存档、正文页都在,清单上勾一下就回来 —— 和「仅提及」
# 同一条规矩。没打过分的不算低分:没有分和低分是两回事。
LOW_SCORE_THRESHOLD = 60


def _is_low_score(row: dict[str, Any]) -> bool:
    score = row.get("score")
    return isinstance(score, int) and score < LOW_SCORE_THRESHOLD


def _score_badge(row: dict[str, Any]) -> str:
    """标题后面那个分。**没打过分就什么都不挂** —— 空分数和 0 分是两回事。"""
    if not isinstance(row.get("score"), int):
        return ""
    return f'<span class="score">{int(row["score"])}</span>'


def _score_card(row: dict[str, Any]) -> str:
    """正文页开头的评分卡:总分、各维度、一句依据。

    9-01 站长:「正文内,首先显示评分依据」。裸数字解释不了自己 —— 分从哪来、
    哪一维拖了后腿,都得摆在分数旁边。打分失败的照实给原话,不藏。
    """
    from inews import score as score_module

    if isinstance(row.get("score"), int):
        dims = "".join(
            f'<span class="dim">{escape(label)} {value}</span>'
            for label, value in score_module.display_dimensions(row)
        )
        notes = str(row.get("score_notes") or "").strip()
        return (
            '<div class="scorecard"><b>评分依据</b>'
            f'<span class="score">{int(row["score"])}</span>'
            f'<p class="dims">{dims}</p>'
            + (f"<p>{escape(notes)}</p>" if notes else "")
            + "</div>"
        )
    if row.get("score_error"):
        return (
            '<div class="scorecard scorecard--failed"><b>评分依据</b>'
            f'<p>未打分:{escape(str(row["score_error"]))}</p></div>'
        )
    return ""


def _keyword_tags(row: dict[str, Any]) -> str:
    return "".join(
        f'<span class="kw">{escape(word)}</span>'
        for word in row.get("keywords", [])
    )


def _when(row: dict[str, Any]) -> tuple[str, str, str]:
    """(日期, 时分, 原始串);读不到时间就照说「时间未知」,不猜。"""
    parsed = parse_datetime(row.get("published_at", ""))
    if not parsed:
        return "时间未知", "", ""
    return (
        parsed.strftime("%Y-%m-%d"),
        parsed.strftime("%H:%M"),
        row.get("published_at", ""),
    )


def _body_html(row: dict[str, Any]) -> str:
    body = str(row.get("body") or "")
    if not body:
        reason = str(row.get("body_error") or "未尝试抓取正文")
        return (
            '<div class="failed"><b>正文未取到</b>'
            f"{escape(reason)}</div>"
        )
    paragraphs = [line.strip() for line in body.splitlines() if line.strip()]
    return "".join(f"<p>{escape(line)}</p>" for line in paragraphs)


def render_article(row: dict[str, Any], *, site_label: str = "FT.COM",
                   site_key: str = "ft") -> str:
    """一篇文章一页:标题、时间、原文链接、正文或失败原话。"""
    day, clock, raw = _when(row)
    stamp = f"{day} {clock}".strip() if raw else day
    section = row.get("section", "")
    head = (
        f'<a class="back" href="{layout.PAGE_PREFIX}index.html">← 回到清单</a>'
        # 中文当标题、英文原题跟在下面 —— 和清单同一条规矩(9-01 站长指定);
        # 原题必须还在页面上:核对时要看得到站方给的那一串。
        f"<h1>{escape(_title(row))}</h1>"
        + _original_line(row)
        + f'<p class="byline"><span>{escape(stamp)}</span>'
        + (f"<span>{escape(section)}</span>" if section else "")
        + f'<a class="src" href="{escape(row["url"])}">{escape(site_label)} 原文 ↗</a></p>'
        f'<p class="tags">{_keyword_tags(row)}</p>'
    )
    return _page(
        _title(row) or site_label,
        # 评分卡在正文前:9-01 站长指定的次序 —— 先看这篇值不值得读,再读。
        f'<article class="article">{head}{_score_card(row)}'
        f'<div class="body">{_body_html(row)}</div>'
        f'<a class="back" href="{layout.PAGE_PREFIX}index.html">← 回到清单</a></article>',
        site_key=site_key,
        read=True,
        base=layout.PAGE_PREFIX,
        site_label=site_label,
    )


def _domain_var(domain: str) -> str:
    """主题域 → 色变量。**按声明顺序取槽**,不按篇数 —— 颜色跟着实体走,
    数据变了每条线的颜色也不该跟着换。"""
    names = [name for name in kw.DOMAINS if name != kw.OTHER_DOMAIN]
    if domain in names:
        return f"var(--domain-{names.index(domain) + 1})"
    return "var(--domain-other)"


def _dot(domain: str) -> str:
    return f'<i class="dot" style="background:{_domain_var(domain)}"></i>'


def _domain_legend() -> str:
    """图例:两个以上的系列同屏就必须有它,而且名字要写全。"""
    items = "".join(
        f'<span class="legend__key">{_dot(name)}{escape(name)}</span>'
        for name in kw.DOMAINS
    )
    return f'<div class="legend">{items}</div>'


def _groups_of(row: dict[str, Any]) -> list[str]:
    return sorted({kw.group_of(word) for word in row.get("keywords", [])})


def _controls(groups: list[str]) -> str:
    boxes = "".join(
        f'<label><input type="checkbox" value="{escape(name)}"> {escape(name)}</label>'
        for name in groups
    )
    return (
        '<div class="controls">'
        '<input type="search" id="q" placeholder="按标题筛选">'
        f"{boxes}"
        # 提及型默认藏。**藏不是删**:台账、存档、HTML 里都在,勾一下就回来 ——
        # 「我这会儿不想看」不能变成「再也看不到」。
        '<label><input type="checkbox" id="mentions"> 显示仅提及</label>'
        # 低分同一条规矩:默认藏、勾一下回来。阈值见 LOW_SCORE_THRESHOLD。
        f'<label><input type="checkbox" id="lowscores"> 显示低分(&lt;{LOW_SCORE_THRESHOLD})</label>'
        '<label><input type="checkbox" id="secondary"> 显示次要/待验证</label>'
        "</div>"
    )


# 每页多少条。默认 50:两三次滚动能扫完一天多的量,又不像 25 那样频繁翻页。
# **「全部」留着** —— 想用浏览器自带的 Ctrl-F 搜整库时,分页是碍事的。
PAGE_SIZES = (25, 50, 100, 0)
DEFAULT_PAGE_SIZE = 50


def _pager() -> str:
    def option(size: int) -> str:
        label = "全部" if size == 0 else str(size)
        mark = " selected" if size == DEFAULT_PAGE_SIZE else ""
        return f'<option value="{size}"{mark}>{label}</option>'

    return (
        '<div class="pager"><label for="pagesize">每页</label>'
        f'<select id="pagesize">{"".join(option(size) for size in PAGE_SIZES)}</select>'
        '<span id="pageinfo" class="pager__info">—</span>'
        '<span class="pager__nav">'
        '<button type="button" id="prev">← 上一页</button>'
        '<button type="button" id="next">下一页 →</button>'
        "</span></div>"
    )


def _wan(chars: int) -> str:
    """字数按「万字」报。七位数要人一位一位地数,而这个数字只用来估量级。"""
    return f"{chars // 10000} 万字" if chars >= 10000 else f"{chars} 字"


def _cell(value: str, label: str, extra: str = "", *, bad: bool = False) -> str:
    """总览里的一格。**每格结构都一样** —— 值、标签、可选的一条图形。

    结构不一样就对不齐:8-24 站长指的「都没有对齐」,根子是每块自己排自己的。
    """
    mark = ' class="bad"' if bad else ""
    return (
        '<div class="cell">'
        f"<strong{mark}>{escape(value)}</strong>"
        f"<span>{escape(label)}</span>"
        f'<div class="cell__art">{extra}</div>'
        "</div>"
    )


def _cover_bar(got: int, failed: int, rest: int) -> str:
    """正文覆盖:取到 / 失败 / 还没取。比例要看得见,不是让人拿两个数去心算。"""
    total = max(1, got + failed + rest)
    parts = (("ok", got), ("bad", failed), ("rest", rest))
    return '<div class="cover">' + "".join(
        f'<i class="cover--{cls}" style="width:{count * 100 // total}%"></i>'
        for cls, count in parts if count
    ) + "</div>"


def _axis(days: list[str], generated_at: str) -> str:
    """一条覆盖时间轴:**真实最早的那篇** → 最新。

    不写硬地板:那是「最早允许抓到哪」,不是「实际抓到了哪」—— 把政策上限画成
    事实,看的人会以为库里真有那么早的稿子。硬地板在后台「进度」卡上,明写着
    「硬地板」。空的就说空的,不画一条假的满条。
    """
    if not days:
        return ""
    return (
        '<div class="spanline"><span>' + escape(days[0]) + "</span>"
        '<i></i><span>' + escape(days[-1]) + "</span></div>"
    )


def _span_days(days: list[str]) -> int:
    """最早到最新差几天。读不出就当 0 —— 不猜。"""
    start, end = parse_datetime(days[0]), parse_datetime(days[-1])
    if not start or not end:
        return 0
    return max(1, (end - start).days + 1)


def _library_band(rows: list[dict[str, Any]], body_chars: int) -> str:
    got = sum(1 for row in rows if stats_module.has_body(row))
    failed = sum(
        1 for row in rows
        if not stats_module.has_body(row) and stats_module.body_failed(row)
    )
    rest = max(0, len(rows) - got - failed)
    words = len({word for row in rows for word in row.get("keywords", [])})
    groups = len({name for row in rows for name in _groups_of(row)})
    days = sorted({_when(row)[0] for row in rows if _when(row)[2]})
    span = f"{days[0]} → {days[-1]}" if days else "时间未知"
    cells = [
        _cell(str(len(rows)), "库内篇数", _cover_bar(got, failed, rest)),
        # 大数字放**天数**,区间放在下面那条时间轴上:一串 "2026-08-10 → 2026-08-21"
        # 挤在一格里只会被截成 "2026-08-10 → 2…",截断之后它什么也没说。
        _cell(f"{_span_days(days)} 天" if days else "—", "覆盖区间", _axis(days, "")),
        _cell(f"{groups} 组 / {words} 词", "话题"),
        # 一篇都没有正文时不报「0 万字」—— 那看起来像抓到了一堆空文章。
        _cell(_wan(body_chars) if body_chars else "—", "正文字数"),
        _cell(str(got), "已取到正文", _cover_bar(got, 0, rest + failed)),
        _cell(str(failed), "取正文失败", _cover_bar(0, failed, got + rest), bad=failed > 0),
    ]
    return (
        '<section class="band"><div class="band__head"><span>原文库</span>'
        f"<em>{escape(span)}</em></div>"
        f'<div class="band__grid band__grid--6">{"".join(cells)}</div></section>'
    )


def _round_band(runs: list[dict[str, Any]], new_count: int | None) -> str:
    """最近一轮发现时做了什么。失败数是当时的历史事实,手动
    修复之后不篡改;**当前**还失败几篇由上面的「原文库」回答。

    没有跑批记录时**不编**:那几格就写「还没有跑过」。
    """
    latest = runs[-1] if runs else {}
    if not runs:
        cells = [_cell("还没有跑过", "本轮", "")]
        return (
            '<section class="band"><div class="band__head"><span>最近一轮发现</span>'
            "<em>还没有跑过</em></div>"
            f'<div class="band__grid band__grid--1">{"".join(cells)}</div></section>'
        )
    hits = int(latest.get("hits") or 0)
    fresh = int(latest.get("new") or 0) if new_count is None else int(new_count)
    processed = int(latest.get("processed") or 0)
    failed = int(latest.get("body_failed") or 0)
    backlog = int(latest.get("backlog") or 0)
    cells = [
        _cell(str(hits), "本轮命中"),
        _cell(str(fresh), "入库新增"),
        _cell(str(processed), "取正文", _cover_bar(processed - failed, failed, 0)),
        _cell(str(failed), "当轮正文失败", bad=failed > 0),
        _cell(str(backlog), "待下轮处理"),
        _cell(escape(str(latest.get("finished_at", "")))[11:19] or "—", "跑完于"),
    ]
    return (
        '<section class="band"><div class="band__head"><span>最近一轮发现</span>'
        f'<em>{escape(str(latest.get("finished_at", "")))}</em></div>'
        f'<div class="band__grid band__grid--6">{"".join(cells)}</div></section>'
    )


_RUN_COMMAND = "bash tools/hourly.sh"
# 本机监听的地址。**只可能是回环** —— 见 serve.py 开头那段边界。
_RUN_ENDPOINT = "http://127.0.0.1:8787/run"
_SERVE_ORIGIN = "http://127.0.0.1:8787"


def _actions_for(site_key: str) -> dict[str, str]:
    """这一页那两个按钮各自敲哪条路径、监听没开时该把哪条命令交到手上。

    ft 用不带后缀的路径:那是 8-28 就在跑的那条,改路径等于让老页面上的按钮
    在新监听上变成 404。加站只在这里多一个后缀,和 serve.ACTIONS 一一对应。
    """
    suffix = "" if site_key == "ft" else f"/{site_key}"
    return {
        "run": f"{_SERVE_ORIGIN}/run{suffix}",
        "run_cmd": "bash tools/hourly.sh" + (f" {site_key}" if site_key != "ft" else ""),
        "repair": f"{_SERVE_ORIGIN}/repair{suffix}",
        "repair_cmd": f"bash tools/repair.sh {site_key}",
    }
_STALE_HOURS = 3  # 每小时一轮的东西超过三小时没动,就该有人去看一眼
_SHOW_RUNS = 5    # 「前几次」就到 5 为止:再往前对「它还在跑吗」没有帮助


def _minutes_between(then: str, now_text: str) -> int | None:
    start, end = parse_datetime(then), parse_datetime(now_text)
    if not start or not end:
        return None
    minutes = int((end - start).total_seconds() // 60)
    return minutes if minutes >= 0 else None


def _cadence(
    runs: list[dict[str, Any]],
    generated_at: str,
    *,
    site_key: str = "ft",
    broken: int = 0,
) -> str:
    """最近 5 轮 + 「抓一轮」按钮。

    为什么清单页也要有(后台已经有健康灯):**定时静默停摆是这个项目最坏的失败
    形态** —— 页面照旧、退出码正常,只有「距上一轮」这个数字不再变小。站长每天
    看的是清单页,那这句话就得写在清单页上。
    """
    # 显示频率也从唯一时刻表读。Reuters/Axios 隔小时轮换后，页面若仍写
    # “每小时一轮”会把正常的 2 小时间隔误报成停摆。
    from inews.schedule import cadence_for_site

    schedule_text = cadence_for_site(site_key)
    recent = runs[-_SHOW_RUNS:]
    if not recent:
        head = "<em>还没有跑过</em>"
    else:
        gap = _minutes_between(str(recent[-1].get("finished_at", "")), generated_at)
        fails = runlog.consecutive_failures(runs)
        if fails:
            # 失败留原话:兜底文案顶掉真实错误是这个仓库反复出事的地方。
            reason = escape(runlog.last_error(runs) or "未记录原因")
            head = f'<em class="bad">连续 {fails} 轮失败 · {reason}</em>'
        elif gap is None:
            head = "<em>距上一轮:时间未知</em>"
        elif gap > _STALE_HOURS * 60:
            since = escape(_since(str(recent[-1].get("finished_at", "")), generated_at))
            head = f'<em class="bad">定时可能停了 · 距上一轮 {since}</em>'
        else:
            head = f"<em>{escape(schedule_text)} · 距上一轮 {gap} 分钟</em>"
    top = max([int(entry.get("new") or 0) for entry in recent] or [1]) or 1
    items = "".join(
        '<li class="{cls}"><b>{at}</b>'
        '<span class="runbar"><i style="width:{pct}%"></i></span>'
        "<span>新增 {new}</span><span>命中 {hits}</span>{err}</li>".format(
            cls="" if entry.get("ok") else "bad",
            at=escape(str(entry.get("finished_at", ""))[:19] or "时间未知"),
            # 0 也画一条细的:「那轮是 0」和「那轮没跑」必须看得出区别。
            pct=max(2, int(entry.get("new") or 0) * 100 // top),
            new=int(entry.get("new") or 0),
            hits=int(entry.get("hits") or 0),
            err=(
                ""
                if entry.get("ok")
                else f'<em>{escape(str(entry.get("error") or "未记录原因"))}</em>'
            ),
        )
        for entry in reversed(recent)
    ) or "<li><span>跑一轮之后,这里会列出最近 5 轮的时间</span></li>"
    action = _actions_for(site_key)
    # 一篇都没失败时不摆「修复未抓取」:一个按下去什么也不会发生的按钮,比没有
    # 更糟 —— 它让人以为自己漏做了什么。有几篇失败就把数目写在按钮上。
    repair = (
        f'<button id="repair" type="button" data-endpoint="{escape(action["repair"])}" '
        f'data-cmd="{escape(action["repair_cmd"])}">修复未抓取 · {broken} 篇</button>'
        if broken
        else ""
    )
    return (
        '<section class="band cadence"><div class="band__head">'
        f"<span>最近 {len(recent)} 轮抓取</span>{head}</div>"
        '<div class="cadence__body"><ol>' + items + "</ol>"
        '<div class="cadence__run">'
        f'<button id="run" type="button" data-endpoint="{escape(action["run"])}" '
        f'data-cmd="{escape(action["run_cmd"])}">抓一轮</button>'
        + repair
        + f"<p>按下去会敲你自己那台机器上的监听(<code>{escape(_SERVE_ORIGIN)}</code>),"
        f"由它启动 <code>{escape(action['run_cmd'])}</code> —— 页面本身是静态的,"
        "抓取只在本机执行；需要登录态的来源会按自己的档位打开浏览器。监听没开时按钮不会假装成功,"
        "而是把对应命令复制给你。"
        + (
            "「修复未抓取」只重取那几篇正文失败的,**不搜索**;"
            "自动重试按 6/24/72 小时退避,试满之后就只等这个按钮。"
            if broken
            else ""
        )
        + "</p></div></div></section>"
    )


def _notes(notes: list[str] | None) -> str:
    """本轮记录:**一条都不丢**,但也不能整片摊在页顶把正文挤下去。

    失败留在外面(那是要被看见的那几条),常规记录折进 ``<details>``。
    「失败」两个字是 ``run.collect`` 写记录时的固定措辞,用例把它钉住了。
    """
    if not notes:
        return ""
    bad = [note for note in notes if "失败" in note]
    rest = [note for note in notes if "失败" not in note]
    head = (
        '<div class="log__head"><span>本轮记录</span>'
        f"<span>{len(notes)} 条 · 失败 {len(bad)}</span></div>"
    )
    body = ""
    if bad:
        body += '<div class="log__bad">' + "".join(
            f"<p>{escape(note)}</p>" for note in bad
        ) + "</div>"
    if rest:
        body += (
            f"<details><summary>展开其余 {len(rest)} 条</summary>"
            '<div class="log__all">'
            + "".join(f"<p>{escape(note)}</p>" for note in rest)
            + "</div></details>"
        )
    return f'<section class="log">{head}{body}</section>'


# 每小时那一轮的间隔。超过这个数就不是「刚跑过」,是该有人去看一眼。
# 3 而不是 1:固定分钟任务可能因资源组排队而推迟；系统唤醒也只会把同一任务
# 错过的多个 CalendarInterval 合并成一次，阈值卡在 1 小时会制造误报。
def render_index(
    rows: list[dict[str, Any]],
    *,
    keywords: list[str],
    generated_at: str,
    order: str = "newest",
    notes: list[str] | None = None,
    new_count: int | None = None,
    linkable: set[str] | None = None,
    runs: list[dict[str, Any]] | None = None,
    body_chars: int = 0,
    site_label: str = "FT.COM",
    tagline: str = "AI 关键词清单",
    rules: tuple[str, ...] | list[str] = (),
    site_key: str = "ft",
) -> str:
    """清单页:按天分组的时间线,加浏览器本地的筛选。

    筛选不缩小抓取范围 —— **宽口径召回是站长要的**,窄的是当下这一眼要看的东西。
    两者混同,就会把「我这会儿不想看」变成「以后再也抓不到」。
    """
    items: list[str] = []
    current_day = ""
    # **不编号。** 右边那个 01/02 只是「第几行」:筛一下就全变了,不指向任何
    # 事实 —— 一个跟着视图变的数字,看的人却会当成它属于这篇稿子。
    for row in rows:
        day, clock, raw = _when(row)
        if day != current_day:
            current_day = day
            items.append(f'<div class="daysep">{escape(day)}</div>')
        # **本地没有的页面不给链接。** 台账记着这一篇,不等于盘上有它的正文页:
        # 2026-08-22 存档上线之前爬的那批正文只存在于 HTML 里,重画画不出来,
        # 清单却照旧链过去 —— 点进去 404。`linkable=None` 表示不做这个判断
        # (纯渲染的调用方不必知道盘上有什么)。
        local = article_filename(row)
        has_page = linkable is None or row.get("article_id", "") in linkable
        words = row.get("keywords", [])
        # 中英都进搜索:清单上看到的是中文,而站长记得住的往往是英文原词。
        haystack = " ".join(
            [row.get("title_en", ""), str(row.get("title_zh") or ""), *words]
        ).lower()
        state = ""
        if not stats_module.has_body(row):
            label = "正文未取到" if stats_module.body_failed(row) else "仅清单"
            kind = "alert" if stats_module.body_failed(row) else "muted"
            state = f'<span class="badge badge--{kind}">{label}</span>'
        if row.get("mention_only") and not row.get("quality_status"):
            # 为什么被降级,写在行上 —— 一行凭空消失或凭空出现都得有解释。
            state += '<span class="badge badge--muted">仅提及</span>'
        quality_status = str(row.get("quality_status") or "")
        if quality_status and quality_status != quality_module.CORE:
            label = quality_module.LABELS.get(quality_status, quality_status)
            kind = "alert" if quality_status == quality_module.OFF_TOPIC else "muted"
            state += (
                f'<span class="badge badge--{kind}" title="'
                f'{escape(str(row.get("quality_reason") or ""))}">{escape(label)}</span>'
            )
        if not has_page:
            state += '<span class="badge badge--muted">无本地页</span>'
        items.append(
            f'<div class="row" data-groups="{escape("|".join(_groups_of(row)))}" '
            + ('data-mention="1" ' if row.get("mention_only") and not quality_status else "")
            + ('data-low="1" ' if _is_low_score(row) and quality_status in ("", quality_module.CORE) else "")
            + (f'data-quality="{escape(quality_status)}" '
               if quality_module.hidden_by_default(row) else "")
            + f'data-search="{escape(haystack)}">'
            # 日期在分隔线上,行内只留时分。站方给的原始时间串仍然逐字进
            # `<time datetime>`:核对时间时要能看到**它给的那一串**,不是我们
            # 格式化后的样子。读不到时间就明写「时间未知」,不给漂亮的占位。
            + f'<time class="when" datetime="{escape(raw)}">{escape(clock or "—")}'
            + ("" if raw else "<span>时间未知</span>")
            + "</time>"
            # 标题和标签在**同一行**:标签原来自己占一行,一百多条就白吃一百多行。
            # 标题在左、标签与来源被推到右边,英文原题另起一行(核对时要看得见)。
            + '<div class="story"><div class="titlerow">'
            + (
                f'<a class="headline" href="{escape(local)}">{escape(_title(row))}</a>'
                if has_page
                else f'<span class="headline headline--gone">{escape(_title(row))}</span>'
            )
            # 分数紧跟标题(9-01 站长指定的版式);依据不挤在清单上,在正文页开头。
            + _score_badge(row)
            + f'<div class="meta">{_keyword_tags(row)}{state}'
            f'<a class="src" href="{escape(row["url"])}">{escape(site_label)} ↗</a></div></div>'
            + _original_line(row)
            + "</div>"
            "</div>"
        )
    all_groups = sorted({name for row in rows for name in _groups_of(row)})
    order_text = "正序(旧 → 新)" if order == "oldest" else "倒序(新 → 旧)"
    stream = (
        _controls(all_groups)
        + '<div class="tallybar">'
        + f'<p class="tally">显示 <b id="shown">{len(rows)}</b> / {len(rows)} 篇</p>'
        + _pager()
        + "</div>"
        + '<section class="stream"><div class="stream__head">'
        f"<span>发布时间 · {escape(order_text)}</span><span>{escape(site_label)}</span></div>"
        + "".join(items)
        + "</section>"
        if rows
        else '<p class="empty">本轮没有命中任何文章</p>'
    )
    body = (
        f'<div class="kicker"><span>{escape(site_label)} · {escape(tagline)}</span>'
        f"<span>{escape(generated_at)}</span></div>"
        f'<div class="hero"><div><h1>{escape(site_label)}<br>{escape(tagline)}</h1>'
        f'<p class="lede">按发布时间{escape(order_text)}排列。'
        + (
            f"库内共 {len(rows)} 篇,来自 {len(keywords)} 个关键词:"
            f"{escape(' / '.join(keywords))}</p></div>"
            if keywords
            # 纯专题页召回的站没有关键词 —— 如实说来源,不摆一个「0 个关键词」。
            else f"库内共 {len(rows)} 篇,全部来自官方栏目页。</p></div>"
        )
        + '<div class="clock"><span>生成于</span>'
        f"<strong>{escape(generated_at)}</strong>"
        '<span>后台</span>'
        '<strong><a href="dashboard.html">dashboard.html →</a></strong></div></div>'
        # 抓取规则印在页面自己身上(9-02 站长:「放在每个页面的上面」)——
        # 每一页都该自己说清「我是怎么来的」,读的人不必去翻仓库源码。
        + (
            '<div class="rules"><span class="rules__head">抓取规则</span><ul>'
            + "".join(f"<li>{escape(str(line))}</li>" for line in rules)
            + "</ul></div>"
            if rules
            else ""
        )
        + _library_band(rows, body_chars)
        + _round_band(runs or [], new_count)
        + _cadence(
            runs or [], generated_at, site_key=site_key,
            broken=sum(1 for row in rows if stats_module.body_failed(row)),
        )
        + _notes(notes)
        + stream
    )
    return _page(
        f"{site_label} · {tagline}",
        body,
        # 按钮在有没有稿子的时候都要能按 —— 一篇都没有的那一天,正是最需要
        # 手动跑一轮的那一天。
        script=(_FILTER_JS if rows else "") + _RUN_JS,
        site_label=site_label,
        site_key=site_key,
        active="index.html",
    )


def _table(title: str, pairs: list[tuple[str, int]]) -> str:
    """一张「项 / 篇数 / 条形」表。标题由外面的卡片给 —— 表自己不再画 h2。"""
    if not pairs:
        return ""
    top = max(count for _label, count in pairs) or 1
    rows = "".join(
        f"<tr><td>{escape(label)}</td>"
        f'<td class="num">{count}</td>'
        f'<td><span class="bar"><i style="width:{count * 100 // top}%"></i></span></td></tr>'
        for label, count in pairs
    )
    return (
        '<table><thead><tr><th>项</th><th class="num">篇数</th><th></th></tr>'
        f"</thead><tbody>{rows}</tbody></table>"
    )


def _since(then: str, now_text: str) -> str:
    """「上一轮是多久以前」。读不出时间就说读不出,不拿 0 分钟冒充刚跑过。

    链路死掉的第一个症状就是这个数字不再变小,而一串绝对时间戳要人心算才看得
    出来 —— 心算这一步,凌晨三点是不会有人做的。
    """
    start, end = parse_datetime(then), parse_datetime(now_text)
    if not start or not end:
        return "时间未知"
    minutes = int((end - start).total_seconds() // 60)
    if minutes < 0:
        return "时间未知"
    if minutes < 60:
        return f"{minutes} 分钟"
    if minutes < 60 * 48:
        return f"{minutes // 60} 小时"
    return f"{minutes // 1440} 天"


def _lamp(runs: list[dict[str, Any]], generated_at: str = "") -> str:
    """健康灯:先看最近几轮跑成了没有,再看定时任务是否仍在运行。

    **不美化**:连着失败或超过时限没跑都红着,直到它真的好了。仅凭上一轮退出码
    会把「三天前最后一次成功,此后定时任务死了」画成绿色,比没有灯更误导。
    """
    if not runs:
        return (
            '<div class="status"><span class="lamp lamp--idle"></span>'
            "<div><b>还没有跑过</b><span>跑一轮之后这里会显示每轮的结果</span></div></div>"
        )
    latest = runs[-1]
    failures = runlog.consecutive_failures(runs)
    if failures:
        reason = escape(runlog.last_error(runs) or "未记录原因")
        return (
            '<div class="status"><span class="lamp lamp--bad"></span>'
            f"<div><b>连续 {failures} 轮失败</b>"
            f"<span>最近一次:{reason}</span></div></div>"
        )
    last_at = str(latest.get("finished_at", ""))
    gap = _minutes_between(last_at, generated_at)
    if gap is not None and gap > _STALE_HOURS * 60:
        return (
            '<div class="status"><span class="lamp lamp--bad"></span>'
            f"<div><b>定时任务可能停了</b><span>上一轮成功于 {escape(last_at)}"
            f" · 已过去 {_since(last_at, generated_at)}</span></div></div>"
        )
    return (
        '<div class="status"><span class="lamp lamp--ok"></span>'
        f'<div><b>上一轮正常</b><span>{escape(str(latest.get("finished_at", "")))}'
        f' · 新增 {latest.get("new", 0)} 篇 · 命中 {latest.get("hits", 0)} 篇</span></div></div>'
    )


def _spark(runs: list[dict[str, Any]], key: str, limit: int = 40) -> str:
    """最近若干轮的柱形。0 画成一条灰线而不是没有 —— 「那轮是 0」和
    「那轮没跑」必须看得出区别。失败的那轮标红。"""
    recent = runs[-limit:]
    if not recent:
        return '<p class="tally">还没有记录</p>'
    top = max([int(entry.get(key) or 0) for entry in recent]) or 1
    bars = "".join(
        '<i class="{cls}" style="height:{pct}%"></i>'.format(
            cls=("bad" if not entry.get("ok") else ("zero" if not entry.get(key) else "")),
            pct=max(3, int(entry.get(key) or 0) * 100 // top),
        )
        for entry in recent
    )
    return (
        f'<div class="spark">{bars}</div>'
        f'<div class="axis"><span>{len(recent)} 轮前</span><span>峰值 {top}</span>'
        "<span>最近</span></div>"
    )


def _daybars(pairs: list[tuple[str, int]]) -> str:
    if not pairs:
        return '<p class="tally">库里还没有带时间的稿子</p>'
    top = max(count for _day, count in pairs) or 1
    bars = "".join(
        f'<i style="height:{max(3, count * 100 // top)}%" title="{escape(day)}:{count}"></i>'
        for day, count in pairs
    )
    return (
        f'<div class="spark">{bars}</div>'
        f'<div class="axis"><span>{escape(pairs[0][0])}</span><span>峰值 {top}</span>'
        f"<span>{escape(pairs[-1][0])}</span></div>"
    )


def _heatmap(labels: list[str], table: list[tuple[str, list[int]]], top: int = 14) -> str:
    """关键词 × 周。深浅只表示相对密度,不表示「重要」—— 这里不打分。"""
    if not labels or not table:
        return '<p class="tally">还不够画热力图(需要带时间的稿子)</p>'
    peak = max(max(counts) for _word, counts in table) or 1
    # 深浅表示密度,色相表示主题域 —— 两个维度各管各的,不混在一条彩虹里。
    head = "".join(f"<th>{escape(label.split('-W')[-1])}</th>" for label in labels)
    body = ""
    for word, counts in table[:top]:
        colour = _domain_var(kw.domain_of_word(word))
        cells = "".join(
            '<td><i style="opacity:{op};background:{colour}" title="{w} {n} 篇"></i></td>'.format(
                op=round(0.12 + 0.88 * (count / peak), 2) if count else 0.06,
                colour=colour, w=escape(word), n=count,
            )
            for count in counts
        )
        # 词长了会被截断,所以 title 里留全名 —— 截断本身可以接受,
        # 「看不出这行是哪个词」不行。
        body += (
            f'<tr><td class="word" title="{escape(word)}">'
            f"{_dot(kw.domain_of_word(word))}{escape(word)}</td>{cells}</tr>"
        )
    return (
        f'<table class="heat"><thead><tr><th></th>{head}</tr></thead>'
        f"<tbody>{body}</tbody></table>"
        f'<div class="axis"><span>周(ISO)</span><span>最深 = {peak} 篇/周</span></div>'
    )


def _kpis(cells: list[tuple[str, str, bool]]) -> str:
    """指标条:大数字在上、标签在下。**坏的那格标红**,不靠人去比较数字。

    格子复用清单页那一个 `_cell` —— 两页各写一份的时候,改了一边另一边就歪了。
    """
    return '<section class="kpis">' + "".join(
        _cell(value, label, bad=bad) for value, label, bad in cells
    ) + "</section>"


def _stack(parts: list[tuple[str, int, str]]) -> str:
    """一条堆叠条 + 图例。三个数放成一条,比三句话快 —— 但数字仍然写出来。"""
    total = sum(count for _label, count, _cls in parts) or 1
    bars = "".join(
        f'<i class="stack__seg stack__seg--{cls}" style="width:{count * 100 / total:.4f}%"'
        f' title="{escape(label)} {count}"></i>'
        for label, count, cls in parts
        if count
    )
    legend = "".join(
        f'<span class="stack__key"><i class="stack__seg--{cls}"></i>'
        f"{escape(label)} <b>{count}</b></span>"
        for label, count, cls in parts
    )
    return f'<div class="stack">{bars}</div><div class="stack__legend">{legend}</div>'


def _small_multiples(labels: list[str], series: list[tuple[str, list[int]]]) -> str:
    """主题域 × 周,一域一条。**共用同一个纵轴上限**,否则八张图彼此没法比 ——
    一条 2 篇的线和一条 40 篇的线会长得一样高。"""
    if not labels or not series:
        return '<p class="tally">还不够画(需要带时间的稿子)</p>'
    peak = max(max(counts) for _name, counts in series) or 1
    cards = ""
    for name, counts in series:
        bars = "".join(
            '<i style="height:{pct}%;background:{colour}" title="{label} {n} 篇"></i>'.format(
                pct=max(3, count * 100 // peak), colour=_domain_var(name),
                label=escape(labels[i]), n=count,
            )
            for i, count in enumerate(counts)
        )
        cards += (
            f'<div class="mini"><div class="mini__head">{_dot(name)}'
            f"<span>{escape(name)}</span><b>{sum(counts)}</b></div>"
            f'<div class="spark spark--mini">{bars}</div></div>'
        )
    return (
        f'<div class="minis">{cards}</div>'
        f'<div class="axis"><span>{escape(labels[0])}</span>'
        f"<span>共用纵轴 · 峰值 {peak} 篇/周</span><span>{escape(labels[-1])}</span></div>"
    )


def _movers(moves: list[tuple[str, int, int, int]]) -> str:
    """本周对上周。**两个方向都画**:只留上涨的那半边就成了报喜。

    涨用暖色、跌用冷色、零居中 —— 这是极性,不是大小,所以两色 + 中性,
    不是一条渐变。
    """
    if not moves:
        return '<p class="tally">还不够两周,没法比</p>'
    span = max(abs(delta) for _w, delta, _n, _b in moves) or 1
    body = "".join(
        '<tr><td>{dot}{word}</td>'
        '<td class="num">{now}</td><td class="num">{before}</td>'
        '<td class="delta"><span class="delta__rail">'
        '<i class="delta__bar delta__bar--{side}" style="width:{pct}%"></i></span></td>'
        '<td class="num delta__n delta__n--{side}">{sign}{delta}</td></tr>'.format(
            dot=_dot(kw.domain_of_word(word)), word=escape(word),
            now=now, before=before,
            side="up" if delta > 0 else ("down" if delta < 0 else "flat"),
            pct=abs(delta) * 100 // span, sign="+" if delta > 0 else "", delta=delta,
        )
        for word, delta, now, before in moves
    )
    return (
        '<table><thead><tr><th>词</th><th class="num">本周</th>'
        '<th class="num">上周</th><th></th><th class="num">变化</th></tr></thead>'
        f"<tbody>{body}</tbody></table>"
    )


def _pairs(pairs: list[tuple[tuple[str, str], int]]) -> str:
    """常一起出现的词对。同组内配对天然高 —— 那正说明这两个词问的是同一件事。"""
    if not pairs:
        return '<p class="tally">还没有同时挂两个词的稿子</p>'
    # 不画条形:这张表在四栏宽的卡片里,条形只剩一根看不出长短的竖线 ——
    # 一个量不出大小的图形比没有图形更坏。数字自己说得清楚。
    body = "".join(
        f'<tr><td>{_dot(kw.domain_of_word(left))}{escape(left)}</td>'
        f'<td>{_dot(kw.domain_of_word(right))}{escape(right)}</td>'
        f'<td class="num">{count}</td></tr>'
        for (left, right), count in pairs
    )
    return (
        '<table><thead><tr><th>词</th><th>常和它一起</th>'
        '<th class="num">同篇</th></tr></thead>'
        f"<tbody>{body}</tbody></table>"
    )


def _detail_rows(rows: list[dict[str, Any]]) -> str:
    """全部标题 + 正文状态。失败带**服务端原话**,不给兜底文案。"""
    if not rows:
        return '<p class="empty">库里还没有稿子</p>'
    body = ""
    for row in rows:
        day, clock, raw = _when(row)
        if stats_module.has_body(row):
            mark, cls = "✓", "ok"
        elif stats_module.body_failed(row):
            mark, cls = "✗", "bad"
        else:
            mark, cls = "○", "idle"
        why = ""
        if stats_module.body_failed(row):
            why = f'<span class="why">{escape(str(row.get("body_error") or "未记录原因"))}</span>'
        words = " · ".join(row.get("keywords", []))
        body += (
            f'<tr><td class="mark {cls}">{mark}</td>'
            f'<td class="day">{escape(day)}<br>{escape(clock or "—")}</td>'
            f'<td><a href="{escape(article_filename(row))}">{escape(_title(row))}</a>'
            f'{why}<span class="words">{escape(words)}</span></td></tr>'
        )
    return (
        '<table class="rows"><thead><tr><th></th><th>发布</th>'
        "<th>标题 · 关键词</th></tr></thead>"
        f"<tbody>{body}</tbody></table>"
    )


def _card(title: str, note: str, body: str, *, span: int = 4, open_: bool = True) -> str:
    """一张牌。``span`` 是它在 12 栏里占几栏 —— 图占宽的,表占窄的。"""
    head = (
        f'<div class="card__head"><span>{escape(title)}</span>'
        f"<span>{escape(note)}</span></div>"
    )
    if open_:
        return (
            f'<section class="card card--{span}">{head}'
            f'<div class="card__body">{body}</div></section>'
        )
    return (
        f'<section class="card card--{span}">'
        f"<details><summary>{escape(title)} · {escape(note)}</summary>"
        f'<div class="card__body">{body}</div></details></section>'
    )


# 一轮到底做了什么。**图上的每个字都来自代码**,不在这里手抄常量 ——
# 手抄的那份迟早和代码分叉,而分叉的文档比没有文档更坏:它看起来是可信的。
def _stages(site, keywords: list[str]) -> tuple[tuple[str, str, str], ...]:
    """流程图的六个格子。**第一格由这个站的召回立场决定** —— 9-03 之前它写死
    「45 个词 · 8 个语义组」,于是一个关键词都没有的 Bloomberg 后台也这么说。
    数字来自传进来的真实词表,不在这里手抄常量。"""
    if site.SEARCHABLE:
        groups = len({kw.group_of(word) for word in keywords}) if keywords else 0
        first = ("关键词", "keywords.py", f"{len(keywords)} 个词 · {groups} 个语义组")
        second = ("搜索页 / 分类页", f"sites/{site.KEY}.py", "每轮只翻第 1 页")
    else:
        first = ("栏目页", f"sites/{site.KEY}.py",
                 " · ".join(site.HUBS) + " · 编辑判定即召回")
        if site.LISTING_FETCHER is not None:
            second = ("展开更多", f"sites/{site.KEY}.py",
                      "读取 Load more 接口,以总数验完整")
        elif site.HUBS and site.hub_url(site.HUBS[0], 2) != site.hub_url(site.HUBS[0], 1):
            second = ("分页历史河", f"sites/{site.KEY}.py",
                      "按 ?page=N 翻页,每页只读官方主河")
        else:
            second = ("展开更多", "browser/contract.py",
                      "点开 Load more,收完整条河" if site.LOAD_MORE_TEXT else "只收首屏")
    return (
        first,
        second,
        ("台账 ledger.json", "ledger.py", "爬过没有 · 只记状态"),
        ("取正文", "fetch.py", "失败按 6/24/72 小时退避重试"),
        ("存档 articles/*.json", "archive.py", "正文的唯一正本"),
        ("渲染 + 发布", "render.py / publish.sh", "静态 HTML → inews.today"),
    )


def _architecture(site, keywords: list[str]) -> str:
    """一张流程图。

    为什么画图而不是列条目:这条链上「谁先谁后」和「哪一步会开浏览器窗口」是
    两个正交的事实,文字里它们会缠在一起,图上一眼分得开。
    """
    from inews.browser import contract as _contract, tiers as _tiers

    stages = _stages(site, keywords)
    tier_note = (
        "可见窗口,失败不回落"
        if _tiers.requires_visible_browser(site.KEY)
        else "无头窗口,失败不回落"
    )
    width, box_h, gap = 176, 62, 22
    boxes = ""
    for i, (name, where, note) in enumerate(stages):
        x = i % 3 * (width + gap)
        y = i // 3 * (box_h + 46)
        boxes += (
            f'<g transform="translate({x},{y})">'
            f'<rect width="{width}" height="{box_h}" rx="2" class="node"/>'
            f'<text x="10" y="20" class="node__t">{escape(name)}</text>'
            f'<text x="10" y="36" class="node__w">{escape(where)}</text>'
            f'<text x="10" y="52" class="node__n">{escape(note)}</text>'
            "</g>"
        )
        # 箭头:同一行往右,行末往下折回最左。
        if i < len(stages) - 1:
            if i % 3 == 2:
                # 行末:往下折回最左边那一列的顶上。
                down = (
                    f'M{x + width // 2} {y + box_h} v14 '
                    f'H{width // 2} v18'
                )
                boxes += f'<path class="edge" d="{down}" marker-end="url(#a)"/>'
            else:
                across = f'M{x + width} {y + box_h // 2} h{gap}'
                boxes += f'<path class="edge" d="{across}" marker-end="url(#a)"/>'
    total_w = 3 * width + 2 * gap
    total_h = 2 * (box_h + 46) - 46 + 4
    return (
        f'<svg class="arch" viewBox="0 0 {total_w} {total_h}" '
        f'role="img" aria-label="inews 抓取链路">'
        '<defs><marker id="a" viewBox="0 0 8 8" refX="7" refY="4" markerWidth="7" '
        'markerHeight="7" orient="auto"><path d="M0 0 L8 4 L0 8 z" class="edge__h"/>'
        "</marker></defs>"
        f"{boxes}</svg>"
        '<dl class="kv kv--wide">'
        f"<dt>能读谁</dt><dd>browser/contract.py 的域名表 · {escape(site.LABEL)} 是 "
        f"{escape(_contract.SITE_DOMAINS.get(site.KEY, ''))}</dd>"
        f"<dt>怎么读</dt><dd>browser/tiers.py 的档位 · {escape(site.LABEL)} 是 "
        f"{escape(_tiers.tier_of(site.KEY))}({escape(tier_note)})</dd>"
        f"<dt>读到多早</dt><dd>sites/{escape(site.KEY)}.py 的硬地板 "
        f"{escape(site.EARLIEST)} —— --since 只能把窗口收得更窄</dd>"
        "</dl>"
    )


# 全项目通用的那几条纪律 —— **和抓哪个站无关**,所以每个库的后台都该有。
# 站点自己的规则住在 sites/<站>.py 的 RULES 里(清单页顶上印的也是那一份),
# 一处实现两处用:后台把两者并排,读的人分得出「这是这个库的立场」和
# 「这是整个项目的纪律」。
_HOW = (
    ("固定日历错峰", "launchd 按每站登记的日历调用采集脚本；站点锁挡同站重入，"
     "资源组锁让可见 Chrome 与公开无头任务各自最多并发一条。"),
    ("失败不回落", "manual 档只走有头窗口，headless 档只走无头窗口；当前档位取不到就如实"
     "失败,绝不偷偷换一档再试 —— 回落等于让「静默」这个承诺失效。"),
    ("失败留原话", "服务端说了什么就显示什么,不给兜底文案。兜底文案顶掉真实错误,"
     "是这个仓库反复出事的地方。"),
    ("取不到就退避重试", "6 / 24 / 72 小时各试一次,试满交给页面上那个「修复未抓取」——"
     "每轮硬试是白开窗口,一次失败就永别又会让一次登录态过期留下永久空白。"),
    ("不猜时间", "读不到发布时间就写「时间未知」。一个猜出来的时间会让整条时间线失真,"
     "而且没人看得出它是猜的。"),
)


def _how_it_works(site) -> str:
    """这个库的规则 + 全项目的纪律。站点那几条来自 ``site.RULES`` —— 和清单页
    顶上印的是同一份,改一处两处都跟着变。"""
    own = "".join(
        f'<dt class="own">这个库</dt><dd>{escape(str(rule))}</dd>'
        for rule in getattr(site, "RULES", ())
    )
    return '<dl class="kv kv--wide">' + own + "".join(
        f"<dt>{escape(title)}</dt><dd>{escape(text)}</dd>" for title, text in _HOW
    ) + "</dl>"


def render_dashboard(
    rows: list[dict[str, Any]],
    *,
    generated_at: str,
    keywords: list[str],
    runs: list[dict[str, Any]],
    notes: list[str] | None = None,
    floor: str = "",
    site_label: str = "",
    tagline: str = "",
    site=None,
    libraries: list[dict[str, Any]] | None = None,
) -> str:
    """后台页:一屏之内看完链路、进度和产出形状。

    ``site`` 是站点模块:页面上每一句关于「这个库怎么抓」的话都从它来 ——
    9-03 之前这里写死 FT,于是 Bloomberg 的后台整页都在说别人的事。

    ``libraries`` 是**各库的一行摘要**,由编排层从盘上读好再交进来:
    render 不碰盘(见模块开头),而跨库对比需要姊妹库的台账。

    排在最上面的永远是**链路死没死** —— 后台页存在的第一理由是让「三天没抓到
    东西」这件事在三天内被看见,而不是等某天想起来翻日志。

    **能画成图的不写成句子,能收起来的不摊在第一屏。** 全部标题和本轮记录都是
    「出事之后才翻」的东西,折起来;数字和图是「每次都要扫一眼」的,摊开。
    一屏塞满段落等于没有后台:该被看见的那一条会淹在里面。
    """
    if site is None:
        from inews.sites import ft as site  # 老调用方不传站点时的缺省
    site_label = site_label or site.LABEL
    tagline = tagline or site.TAGLINE
    earliest, latest = stats_module.coverage(rows)
    got = sum(1 for row in rows if stats_module.has_body(row))
    failed = sum(
        1 for row in rows if not stats_module.has_body(row) and stats_module.body_failed(row)
    )
    idle = len(rows) - got - failed
    rate = f"{got * 100 // len(rows)}%" if rows else "—"
    backlog = int(runs[-1].get("backlog") or 0) if runs else 0
    per_round = int(runs[-1].get("processed") or 0) if runs else 0
    left = f"{-(-backlog // per_round)}" if per_round else "—"
    fails = runlog.consecutive_failures(runs)
    last_new = runs[-1].get("new", 0) if runs else "—"
    quality_counts = quality_module.summary(rows)
    quality_hidden = sum(
        quality_counts[name]
        for name in (
            quality_module.SECONDARY, quality_module.UNVERIFIED,
            quality_module.OFF_TOPIC,
        )
    )

    kpis = _kpis([
        (str(len(rows)), "库内篇数", False),
        (str(last_new), "上轮新增", False),
        (rate, "正文成功率", bool(rows) and got * 100 // max(len(rows), 1) < 80),
        (str(failed), "取正文失败", failed > 0),
        (str(backlog), "积压待抓", False),
        (left, "还需轮次", False),
        (str(len(runs)), "已跑轮次", False),
        (str(fails), "连续失败", fails > 0),
        (str(quality_counts[quality_module.CORE]), "默认核心", False),
        (str(quality_counts[quality_module.UNVERIFIED]), "待验证", quality_counts[quality_module.UNVERIFIED] > 0),
        (str(quality_hidden), "编辑折叠", quality_hidden > 0),
    ])

    labels, table = stats_module.keyword_weeks(rows)
    last_at = str(runs[-1].get("finished_at", "")) if runs else ""
    board = "".join([
        _card("链路", f"距上一轮 {_since(last_at, generated_at)}" if runs else generated_at,
              _lamp(runs, generated_at) + _spark(runs, "new"), span=4),
        _card(
            "正文状态",
            f"覆盖 {earliest or '—'} → {latest or '—'}",
            _stack([("已取到", got, "ok"), ("仅清单", idle, "idle"), ("失败", failed, "bad")])
            + _daybars(stats_module.by_day(rows)),
            span=4,
        ),
        _card(
            "进度",
            f"硬地板 {floor}",
            '<dl class="kv">'
            f"<dt>关键词</dt><dd>{len(keywords)}</dd>"
            f"<dt>已覆盖</dt><dd>{escape(earliest or '—')} → {escape(latest or '—')}</dd>"
            f"<dt>上轮命中</dt><dd>{runs[-1].get('hits', 0) if runs else '—'}</dd>"
            f"<dt>上轮处理</dt><dd>{per_round or '—'}</dd>"
            "</dl>",
            span=4,
        ),
        _card(
            "编辑准入",
            "宽召回不等于默认展示",
            _stack([
                ("核心", quality_counts[quality_module.CORE], "ok"),
                ("次要", quality_counts[quality_module.SECONDARY], "idle"),
                ("待验证", quality_counts[quality_module.UNVERIFIED], "idle"),
                ("主题不符", quality_counts[quality_module.OFF_TOPIC], "bad"),
            ]),
            span=4,
        ),
        _card("架构 · 一轮走过的路", "每个格子对应仓库里的一个文件",
              _architecture(site, keywords), span=8),
        _card("抓取逻辑", "每一条都记着一次真实的权衡", _how_it_works(site), span=4),
        # 跨库对比排在架构之后:先看清「这个库怎么抓」,再看「和别的库比如何」。
        _card("跨库 · 各库一行", "数据从本机各库的台账读来",
              _libraries(libraries or [], site.KEY), span=12),
        # 下面这几张牌的每个数字都来自词表 —— 没有搜索线的库根本没有词表,
        # 画出来只会是「单词:Bloomberg 专题」这种把专题标签当关键词的噪声。
        # 9-03 站长:「后台还是只针对 ft.com 的」,这也是其中一处。
        *((
            _card("主题域 × 周", "共用纵轴 · 八个域各一条",
                  _small_multiples(*stats_module.domain_weeks(rows)) + _domain_legend(),
                  span=8),
            _card("本周对上周", "涨与跌都画,只报差值不解释",
                  _movers(stats_module.week_over_week(rows)), span=4),
            _card("关键词 × 周", "前 14 个词 · 深浅只表示相对密度",
                  _heatmap(labels, table), span=8),
            _card("常一起出现", "同一篇里同时挂着这两个词",
                  f'<div class="scroll">{_pairs(stats_module.co_occurrence(rows))}</div>',
                  span=4),
        ) if site.SEARCHABLE else (
            _card("每周入库", "这个库没有词表,看的是量本身",
                  _movers(stats_module.week_over_week(rows)), span=12),
        )),
        # 「是不是同一个原因」是站长每次看到失败数都会问的第一句话。
        # 原话来自台账,归类判据是 fetch.py 自己生成的固定措辞 —— 结构性事实。
        _card("取正文失败 · 原因", f"{failed} 篇",
              _table("原因", stats_module.by_failure_reason(rows))
              or '<p class="tally">这一批没有失败</p>', span=4),
        _card(f"{site_label} 栏目", "站方自己的分类,和我们的词表各判各的",
              f'<div class="scroll">{_table("栏目", stats_module.by_section(rows))}</div>',
              span=4),
        # 这张表按「每页新增」排,四十多行 —— 给它滚动框,别让它把右列拉出半屏空白。
        _card("召回来源 · 累计", f"{len(runs)} 轮",
              f'<div class="scroll">{_source_ledger(runs)}</div>', span=8),
        # 原来的「关键词分析」整页搬到这里。**只数结构性事实,不打分** ——
        # 挂在哪些词下、几月发的、正文取到没有,值不值得看是站长自己的判断。
        *(
            _card(title, f"{len(pairs)} 项", f'<div class="scroll">{_table(title, pairs)}</div>',
                  span=6 if title in ("关键词", "语义组") else 3)
            for title, pairs in stats_module.summary(rows).items()
            if site.SEARCHABLE or title not in ("关键词", "语义组")
        ),
        _card(
            "全部标题",
            f"✓ {got} · ✗ {failed} · ○ {idle}",
            _detail_rows(rows),
            span=12,
            open_=False,
        ),
    ])

    body = (
        f'<div class="kicker"><span>{escape(site_label)} · 后台</span>'
        f"<span>{escape(generated_at)}</span></div>"
        + kpis
        + f'<div class="board">{board}</div>'
        + _notes(notes)
    )
    return _page(f"{site_label} · 后台", body, active="dashboard.html",
                 site_label=site_label, site_key=site.KEY)


def render_unified_dashboard(
    snapshots: list[dict[str, Any]], *, generated_at: str
) -> str:
    """所有订阅来源共用的一张后台。

    清单和正文仍按站点分开；只有监控与分析在这里汇总。输入由编排层一次读好，
    渲染层继续保持纯函数。每个站点使用同一组指标和组件，因此新增来源不需要再
    手写一套 dashboard。
    """
    available = [item for item in snapshots if not item.get("missing")]
    articles = sum(len(item["rows"]) for item in available)
    with_body = sum(
        sum(1 for row in item["rows"] if stats_module.has_body(row))
        for item in available
    )
    failed = sum(
        sum(1 for row in item["rows"] if stats_module.body_failed(row))
        for item in available
    )
    backlog = sum(int((item.get("runs") or [{}])[-1].get("backlog") or 0)
                  for item in available)
    unhealthy = sum(
        1 for item in available
        if runlog.consecutive_failures(item.get("runs") or []) > 0
    )
    coverage = f"{with_body * 100 // articles}%" if articles else "—"

    summaries = [item["summary"] for item in snapshots]
    cards = [
        _card(
            "全部来源 · 运行状态",
            "每一行保留自己的时间戳，避免把旧快照误当实时数据",
            _libraries(summaries, ""),
            span=12,
        )
    ]

    for item in available:
        site = item["site"]
        rows = item["rows"]
        runs = item.get("runs") or []
        got = sum(1 for row in rows if stats_module.has_body(row))
        site_failed = sum(1 for row in rows if stats_module.body_failed(row))
        idle = len(rows) - got - site_failed
        quality_counts = quality_module.summary(rows)
        earliest, latest = stats_module.coverage(rows)
        last_at = str(runs[-1].get("finished_at", "")) if runs else ""
        listing = f"{_HOME_URL}rawarticle/{site.KEY}/index.html"
        cards.extend([
            _card(
                f"{site.LABEL} · 运行状态",
                f"距上一轮 {_since(last_at, generated_at)}" if runs else "还没有跑批记录",
                f'<p class="tally"><a href="{escape(listing)}">打开独立清单 →</a></p>'
                + _lamp(runs, generated_at) + _spark(runs, "new"),
                span=4,
            ),
            _card(
                f"{site.LABEL} · 正文状态",
                f"覆盖 {earliest or '—'} → {latest or '—'}",
                _stack([
                    ("已取到", got, "ok"),
                    ("仅清单", idle, "idle"),
                    ("失败", site_failed, "bad"),
                ]) + _daybars(stats_module.by_day(rows)),
                span=4,
            ),
            _card(
                f"{site.LABEL} · 失败原因",
                f"{site_failed} 篇 · 硬地板 {site.EARLIEST}",
                _table("原因", stats_module.by_failure_reason(rows))
                or '<p class="tally">这一库没有失败</p>',
                span=4,
            ),
            _card(
                f"{site.LABEL} · 编辑准入",
                "默认只展示核心层，其他内容仍可展开",
                _stack([
                    ("核心", quality_counts[quality_module.CORE], "ok"),
                    ("次要", quality_counts[quality_module.SECONDARY], "idle"),
                    ("待验证", quality_counts[quality_module.UNVERIFIED], "idle"),
                    ("主题不符", quality_counts[quality_module.OFF_TOPIC], "bad"),
                ]),
                span=4,
            ),
            _card(
                f"{site.LABEL} · 召回来源累计",
                f"{len(runs)} 轮",
                f'<div class="scroll">{_source_ledger(runs)}</div>',
                span=6,
            ),
            _card(
                f"{site.LABEL} · 一轮走过的路",
                "同一套站点协议驱动，站点差异只留在适配器",
                _architecture(site, item.get("keywords") or []),
                span=6,
            ),
        ])
        if site.SEARCHABLE:
            labels, table = stats_module.keyword_weeks(rows)
            cards.extend([
                _card(
                    f"{site.LABEL} · 主题域 × 周",
                    "共用纵轴，颜色只编码主题域",
                    _small_multiples(*stats_module.domain_weeks(rows)) + _domain_legend(),
                    span=8,
                ),
                _card(
                    f"{site.LABEL} · 关键词 × 周",
                    "前 14 个词，深浅表示相对密度",
                    _heatmap(labels, table),
                    span=4,
                ),
            ])

    kpis = _kpis([
        (str(len(available)), "运行中的来源", False),
        (str(articles), "库内文章", False),
        (str(with_body), "已有正文", False),
        (coverage, "正文覆盖率", bool(articles) and with_body * 100 // articles < 80),
        (str(failed), "正文失败", failed > 0),
        (str(backlog), "积压待抓", backlog > 0),
        (str(unhealthy), "异常来源", unhealthy > 0),
        (generated_at[:19], "生成时间", False),
    ])
    body = (
        '<div class="kicker"><span>订阅正文库 · 统一后台</span>'
        f'<span>{escape(generated_at)}</span></div>'
        + kpis
        + f'<div class="board">{"".join(cards)}</div>'
    )
    return _page(
        "订阅正文库 · 统一后台",
        body,
        active=_DASHBOARD_URL,
        site_label="ALL SOURCES",
        site_key="all",
    )


def _libraries(libraries: list[dict[str, Any]], here: str) -> str:
    """各库一行:容量、正文覆盖、积压和最后运行状态。

    **每一行都带自己的时间戳**:这些数字是各库各自上一轮留下的,不是同一时刻的
    快照 —— 不标时间的话,一个昨天就停了的库和一个刚跑完的库在表上长得一样。
    读不到某个库的盘就如实说读不到:一个假的 0 会被当成「那边没抓到东西」。
    """
    if not libraries:
        return '<p class="tally">只有这一个库</p>'
    head = (
        "<tr><th>库</th><th>库内</th><th>正文覆盖</th><th>失败</th><th>积压</th>"
        "<th>上一轮</th><th>上轮新增</th><th>状态</th></tr>"
    )
    body = ""
    for lib in libraries:
        me = ' class="me"' if lib.get("key") == here else ""
        label = escape(str(lib.get("label", "")))
        if lib.get("missing"):
            body += (
                f"<tr{me}><td>{label}</td>"
                '<td colspan="7">本机没有这一库的数据(还没跑过,或产出目录不在这里)</td></tr>'
            )
            continue
        articles = int(lib.get("articles") or 0)
        with_body = int(lib.get("with_body") or 0)
        coverage = f"{with_body * 100 // articles}%" if articles else "—"
        state = "正常" if lib.get("last_ok") is True else (
            "失败" if lib.get("last_ok") is False else "未知"
        )
        body += (
            f"<tr{me}><td>{label}</td>"
            f"<td><b>{articles}</b></td>"
            f"<td>{with_body} · {coverage}</td>"
            f"<td>{int(lib.get('failed') or 0)}</td>"
            f"<td>{escape(str(lib.get('backlog', '—')))}</td>"
            f"<td>{escape(str(lib.get('last_at') or '时间未知')[:19])}</td>"
            f"<td>{lib.get('last_new', '—')}</td><td>{state}</td></tr>"
        )
    return f'<div class="table-scroll"><table class="grid">{head}{body}</table></div>'


def _source_ledger(runs: list[dict[str, Any]]) -> str:
    """召回来源的累计账:每条线花了多少页,换回多少入库新增。

    **这张表不下结论。** 「站内搜索比分类页高效」是个待验证的猜想,不是判据;
    这里只把成本(页数)和产出(入库新增)并排放着,让几周之后的真账说话。
    首次归属有顺序偏向(先跑的线占便宜),看的时候要记着这一点。
    """
    totals: dict[str, dict[str, Any]] = {}
    for entry in runs:
        for source in entry.get("sources") or []:
            name = str(source.get("name") or "")
            if not name:
                continue
            bucket = totals.setdefault(
                name, {"kind": source.get("kind", ""), "pages": 0, "hits": 0, "new": 0}
            )
            bucket["pages"] += int(source.get("pages") or 0)
            bucket["hits"] += int(source.get("hits") or 0)
            bucket["new"] += int(source.get("ledger_new") or 0)
    if not totals:
        return '<p class="tally">还没有跑批记录 —— 跑几轮之后这里才有账可看</p>'
    ranked = sorted(
        totals.items(),
        key=lambda item: (
            -(item[1]["new"] / item[1]["pages"] if item[1]["pages"] else 0),
            -item[1]["new"],
        ),
    )
    body = "".join(
        f'<tr><td>{escape(name)}</td>'
        f'<td class="num">{"搜索" if data["kind"] == "search" else "分类页"}</td>'
        f'<td class="num">{data["pages"]}</td>'
        f'<td class="num">{data["new"]}</td>'
        f'<td class="num">{(data["new"] / data["pages"]):.2f}</td></tr>'
        if data["pages"]
        else (
            f'<tr><td>{escape(name)}</td>'
            f'<td class="num">{"搜索" if data["kind"] == "search" else "分类页"}</td>'
            f'<td class="num">0</td><td class="num">{data["new"]}</td>'
            '<td class="num">—</td></tr>'
        )
        for name, data in ranked
    )
    return (
        '<table><thead><tr><th>来源</th><th class="num">类型</th>'
        '<th class="num">开页</th><th class="num">入库新增</th>'
        '<th class="num">每页新增</th></tr></thead>'
        f"<tbody>{body}</tbody></table>"
    )
