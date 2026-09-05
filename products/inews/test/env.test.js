import { test } from 'node:test';
import assert from 'node:assert/strict';
import { mkdtempSync, rmSync, writeFileSync } from 'node:fs';
import { join } from 'node:path';
import { tmpdir } from 'node:os';
import { envValue } from '../src/lib/env.js';
import { assertDatabaseFilenameReady, resolveDbPath } from '../src/lib/db.js';

test('canonical and legacy names may coexist only when their values match', () => {
  assert.equal(envValue('INEWS_DB_PATH', {
    legacy: 'SINGLETITLE_DB', source: { INEWS_DB_PATH: '/data/inews.sqlite3' },
  }), '/data/inews.sqlite3');
  assert.equal(envValue('INEWS_DB_PATH', {
    legacy: 'SINGLETITLE_DB', source: { SINGLETITLE_DB: '/data/news.db' },
  }), '/data/news.db');
  assert.equal(envValue('INEWS_DB_PATH', {
    legacy: 'SINGLETITLE_DB',
    source: { INEWS_DB_PATH: '/data/inews.sqlite3', SINGLETITLE_DB: '/data/inews.sqlite3' },
  }), '/data/inews.sqlite3');
  assert.throws(() => envValue('INEWS_DB_PATH', {
    legacy: 'SINGLETITLE_DB',
    source: { INEWS_DB_PATH: '/data/inews.sqlite3', SINGLETITLE_DB: '/data/news.db' },
  }), /环境变量冲突/);
});

test('database path uses the application filename inside a configured data directory', () => {
  assert.equal(resolveDbPath({ INEWS_DATA_DIR: '/data' }), '/data/inews.sqlite3');
  assert.equal(resolveDbPath({ SINGLETITLE_DB: '/data/news.db' }), '/data/news.db');
});

test('a legacy news.db beside a missing canonical file is never ignored', () => {
  const dir = mkdtempSync(join(tmpdir(), 'inews-db-name-'));
  try {
    writeFileSync(join(dir, 'news.db'), 'legacy placeholder');
    assert.throws(
      () => assertDatabaseFilenameReady(join(dir, 'inews.sqlite3')),
      /旧数据库仍在/,
    );
  } finally {
    rmSync(dir, { recursive: true, force: true });
  }
});

test('canonical and legacy database files may never coexist silently', () => {
  const dir = mkdtempSync(join(tmpdir(), 'inews-db-split-'));
  try {
    writeFileSync(join(dir, 'news.db'), 'legacy placeholder');
    writeFileSync(join(dir, 'inews.sqlite3'), 'partial migration placeholder');
    assert.throws(
      () => assertDatabaseFilenameReady(join(dir, 'inews.sqlite3')),
      /新旧数据库同时存在/,
    );
  } finally {
    rmSync(dir, { recursive: true, force: true });
  }
});
