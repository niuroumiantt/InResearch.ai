// 相似度聚类的判例。三条「豆包煮拖鞋」来自 2026-08-31 线上实拍 ——
// 同一事件三家措辞各异,精确键聚不上,相似聚类必须聚上;
// 反例保证不同新闻不会被错并进一个抽屉。
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { titleTokens, similar } from '../src/lib/cluster.js';

const sim = (a, b) => similar(titleTokens(a), titleTokens(b));

test('同一事件的不同措辞报道判为同题', () => {
  const a = '"豆包建议开水煮拖鞋"？官方出来辟谣了';
  const b = '"豆包建议煮拖鞋"被证实为摆拍谣言，博主承认故意引导';
  const c = '豆包辟谣"建议煮拖鞋":系博主诱导模型摆拍，非真实回复';
  assert.ok(sim(a, c), 'a~c 应聚');
  assert.ok(sim(b, c), 'b~c 应聚');
});

test('英文同题不同措辞也能聚', () => {
  assert.ok(sim(
    'OpenAI pauses work on new version of ChatGPT after it shows concerning behaviour',
    'OpenAI pauses new ChatGPT version work over concerning behaviour reports',
  ));
});

test('不同新闻不得错并', () => {
  // 同是豆包、同一天,但完全不同的两件事
  assert.ok(!sim(
    '豆包辟谣"建议煮拖鞋":系博主诱导模型摆拍',
    '豆包推出开学季学生优惠,送大学生3个月免费订阅权益',
  ));
  // 同是 OpenAI 发布,不同的发布
  assert.ok(!sim(
    'OpenAI launches teen ChatGPT amid calls for greater child safety',
    'OpenAI launches new enterprise agent platform for developers',
  ));
  // 短标题特征不足,宁可不并
  assert.ok(!sim('AI 芯片', 'AI 芯片大涨'));
});
