import { test } from 'node:test';
import assert from 'node:assert/strict';
import { scoreRelevance } from '../src/lib/relevance.js';

// A real Google News page for the query
//   OpenAI OR Anthropic OR "Google DeepMind" OR Gemini OR Claude OR GPT
// pulled 2026-08-19. Every headline is labelled with the verdict a human
// wants, so tuning the scorer can't silently regress the cases we already
// reasoned about. Add new rows here whenever a bad call shows up in the UI.
const CORPUS = [
  // --- must be accepted ---
  ['OpenAI pausing some model work over safety concerns', true],
  ['OpenAI Pauses Training of New AI Models, Citing Cybersecurity Worries', true],
  ['OpenAI reportedly seeing deeper losses in second quarter while sales grew sequentially', true],
  ['The most interesting takeaway from Anthropic’s design study has nothing to do with proteins', true],
  ['News | From OpenAI to Exa Labs, storied San Francisco building remains a magnet for AI startups', true],
  ['Twist Bio stock up on Anthropic announcement (TWST:NASDAQ)', true],
  ['OpenAI launches teen ChatGPT amid calls for greater child safety', true],
  ['OpenAI Says Replit Is Introducing Free Mode, Powered By GPT‑5.6 Luna', true],
  ['OpenAI pauses work on new version of ChatGPT after it shows concerning behaviour', true],
  ['OpenAI Is Pausing Some Work Due To Safety Concerns After Finding It Could Pose Critical Cybersecurity Risks', true],
  ['First look: Gemini could soon remember details from your screenshots with one tap', true],
  ['Murf AI Says Falcon 2 Voice Model Beats OpenAI, ElevenLabs on Naturalness', true],
  ['Verdict Capital’s Michael Fertik explains why he believes OpenAI may never go public', true],
  ['OpenAI confirms it isn\'t buying a teenager\'s startup, despite cheers for offer at Dublin event', true],
  ['Anthropic poised for IPO before OpenAI by Q4 2026 amid market confidence', true],
  ['Google Gemini x BTS Collaboration: Limited-Time Interactive Features with K-Pop Icons Launched', true],
  // previously under-scored at 2 and hidden: a bare "AI" headline is real news
  ['This may be the first academic profession to see its work taken over by AI', true],

  // --- must be rejected ---
  ['Aries, Taurus, Gemini Horoscope Today for August 20, 2026: Confidence Helps You Make a Move That Could Pay', false],
  ['Claude Allen Edwards', false],
  // course ad, not news — reclassified once the genre filter landed
  ['Master AI project management in six hours with this learning bundle', false],

  // --- 2026-08-31 线上实拍的漏网之鱼(站长在时间线上亲眼看到的) ---
  // NHL 冰球运动员,被 "Claude" 捞进来
  ['距开幕之夜还有 32 天：克劳德·勒米厄 (Claude Lemieux)', false],
  // 荐股导购:词法上全是 AI,体裁上是广告
  ['1 No-Brainer Artificial Intelligence (AI) ETF to Buy With $50 and Hold for the Long Term', false],
  // 校园获奖通稿
  ['西安培华学院在2026 高校人工智能财经案例大赛中斩获佳绩', false],
];

test('real Google News page: every headline gets the intended verdict', () => {
  const wrong = [];
  for (const [title, want] of CORPUS) {
    const { score, relevant } = scoreRelevance({ title, query: 'OpenAI OR Anthropic OR Gemini OR Claude OR GPT' });
    if (relevant !== want) wrong.push(`${want ? 'MISSED' : 'FALSE POSITIVE'} [${score}] ${title}`);
  }
  assert.deepEqual(wrong, [], '\n' + wrong.join('\n'));
});

test('ambiguous names are demoted, not blanket-banned', () => {
  // Claude the model still lands when the headline is about the model.
  assert.ok(scoreRelevance({ title: 'Anthropic ships Claude Opus 5 with longer context' }).relevant);
  assert.ok(scoreRelevance({ title: 'Claude now writes better code than GPT, benchmark finds' }).relevant);
  // Gemini the zodiac sign never does.
  assert.ok(!scoreRelevance({ title: 'Gemini daily horoscope: trust your instincts' }).relevant);
  // Neither does a bare obituary headline.
  assert.ok(!scoreRelevance({ title: 'Claude Allen Edwards' }).relevant);
  assert.ok(!scoreRelevance({ title: 'Gemini Watson Smith' }).relevant);
});

test('known collisions with "AI" stay rejected', () => {
  for (const t of [
    'Allen Iverson says the AI era of basketball is over',
    'Air India flight AI-171 diverted to Mumbai',
    'Avian influenza outbreak forces cull in Iowa',
    'Artificial insemination rates rise among dairy herds',
  ]) assert.ok(!scoreRelevance({ title: t }).relevant, t);
});

test('Kimi Formula One names cannot pass as the Moonshot AI model', () => {
  assert.ok(!scoreRelevance({
    title: 'Schumacher claims Kimi Antonelli will join Ferrari',
  }).relevant);
});

// Seen in the live timeline on 2026-08-20: headlines carrying genuine AI
// keywords whose *genre* is not news. The entity lists accept them on their
// own, so the genre filter is what has to catch these.
test('non-news genres are filtered out', () => {
  for (const t of [
    'AI芯片 (BK2548)讨论区- 股票评论- 股吧交流社区',
    "우리 동네 불편, 내 아이디어로 바꾼다…광명시, 'AI 소셜리빙랩' 참여자 모집",
    '경기도, AI 시대의 육아 주제로 뇌과학자 장동선 박사 초청 강연',
    'Master AI project management in six hours with this learning bundle',
    'Get lifetime access to this AI course bundle, now on sale for $29',
  ]) assert.ok(!scoreRelevance({ title: t }).relevant, `should be filtered: ${t}`);
});

test('genre filter does not swallow real stories that mention events', () => {
  for (const t of [
    'OpenAI opens registration for DevDay 2026 with a new agents track',
    'Nvidia GTC keynote: Rubin ships in Q3, Vera Rubin taped out',
    'Anthropic is now hiring a frontier red team after Claude Opus 5 launch',
  ]) assert.ok(scoreRelevance({ title: t }).relevant, `should survive: ${t}`);
});

// From the live timeline on 2026-08-20. The first one was demoted to score 1
// because "startup" is a context word, which pushed the score off zero and so
// suppressed the bare-"AI" bonus entirely.
test('context words must not suppress the bare-AI signal', () => {
  for (const t of [
    'SpaceX Fails to Acquire AI Startup Cognition AI Inc.',
    'Rogue AI agent incidents fuel push for tech transparency',
    'OpenAI tightens AI security after agents hack into Hugging Face',
    "Google DeepMind's shift to California tests the case for London's AI cluster",
    'European AI startup raises Series B to build a compute cluster',
  ]) assert.ok(scoreRelevance({ title: t }).relevant, `should be kept: ${t}`);
});

test('adding entities did not weaken the known rejections', () => {
  for (const t of [
    'Allen Iverson says the AI era of basketball is over',
    'Air India flight AI-171 diverted to Mumbai',
    'Claude Allen Edwards',
    'Gemini daily horoscope: trust your instincts',
    '고배당 ETF 순자산 8조원대 회복했다',
    '[마켓 프리뷰] 채권금리 불안에 코스피 털썩…환율 1300원대로',
    'Suncorp’s New A$250m Buyback and Leadership Shifts Could Be A Game Changer',
    'AI芯片 (BK2548)讨论区- 股票评论- 股吧交流社区',
  ]) assert.ok(!scoreRelevance({ title: t }).relevant, `should be rejected: ${t}`);
});

test('zodiac traps use word boundaries and do not match AI summaries', () => {
  const summary = scoreRelevance({
    title: 'Analysis: search engine AI summaries debunk false narratives at a lower rate',
  });
  assert.equal(summary.relevant, true);
  assert.ok(!summary.hits.includes('!aries'));

  const zodiac = scoreRelevance({ title: 'Aries horoscope uses AI to predict your week' });
  assert.equal(zodiac.relevant, false);
  assert.ok(zodiac.hits.includes('!aries'));
});
