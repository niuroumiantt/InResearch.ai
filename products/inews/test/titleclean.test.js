// 标题清洗与译文质量闸的判例 —— 样本全部来自线上时间线的真实污染。
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { stripPublisherSuffix } from '../src/lib/normalize.js';
import { translationLooksBad } from '../src/lib/translate.js';

test('尾部竖线标签链被剥掉,正文保留', () => {
  assert.equal(
    stripPublisherSuffix('AI正在缩小出海能力差距连连数字让中小企业也能拥有自己的"AI出海战队"|AI智能|B2B|财联社|Agent|营销'),
    'AI正在缩小出海能力差距连连数字让中小企业也能拥有自己的"AI出海战队"');
  assert.equal(
    stripPublisherSuffix('台湾、AIサーバー不正輸出で9人起訴｜セキュリティ対策Lab'),
    '台湾、AIサーバー不正輸出で9人起訴');
});

test('前缀标签和长段不受影响 —— 只剥尾部短段', () => {
  // 开头的栏目标签是正文的一部分,不动
  assert.equal(stripPublisherSuffix('Opinion | OpenAI is not a normal company'),
    'Opinion | OpenAI is not a normal company');
  // 尾段很长 = 可能是正文,不动
  assert.equal(stripPublisherSuffix('Star Wars | Rogue One retrospective review'),
    'Star Wars | Rogue One retrospective review');
  // 没有竖线的普通标题原样通过
  assert.equal(stripPublisherSuffix('Nvidia beats earnings expectations'),
    'Nvidia beats earnings expectations');
});

test('译文质量闸:夹生饭被拒收', () => {
  // 韩文残留(m2m100 的 ko→zh 常见病)
  assert.ok(translationLooksBad('4개월 공백 끝、AI 컨트롤타워 재가동…李海民的作业是什么?', 'src'));
  // 西里尔夹生字符(「재і동」那个 і)
  assert.ok(translationLooksBad('AI 控制塔 재і동', 'src'));
  // 原样吐回
  assert.ok(translationLooksBad('same text', 'same text'));
  // 正常译文放行(少量假名允许 —— 品牌名里可能有)
  assert.ok(!translationLooksBad('OpenAI 因模型异常行为暂停新版 ChatGPT 开发', 'src'));
  assert.ok(!translationLooksBad('软银数据中心子公司获得 55 亿美元优惠以吸引 OpenAI', 'src'));
});
