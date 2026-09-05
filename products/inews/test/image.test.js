import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { join, dirname } from 'node:path';
import { fileURLToPath } from 'node:url';

const ROOT = join(dirname(fileURLToPath(import.meta.url)), '..');
const dockerfile = readFileSync(join(ROOT, 'Dockerfile'), 'utf8');
const dockerignore = readFileSync(join(ROOT, '.dockerignore'), 'utf8')
  .split('\n').map((l) => l.trim()).filter(Boolean);

// The deploy host clones this repo with a token embedded in the URL, which git
// stores in .git/config. The Dockerfile is `COPY . .`, so anything not ignored
// lands in an image layer — and an image layer is forever, survives export, and
// would carry that credential with it.
test('.git is excluded from the build context', () => {
  assert.ok(dockerignore.includes('.git'), '.dockerignore must list .git');
});

test('the image does not install git or read the repo at runtime', () => {
  assert.doesNotMatch(dockerfile, /apk add[^\n]*\bgit\b/,
    'no git in the image: version comes from the build arg, not from a checkout');
});

test('version is passed in as a build argument', () => {
  assert.match(dockerfile, /ARG GIT_SHA/);
  assert.match(dockerfile, /ENV APP_VERSION=\$GIT_SHA/);
});

test('the database lives on the mounted volume, not the image', () => {
  assert.match(dockerfile, /INEWS_DATA_DIR=\/data/,
    'autopull rebuilds the container on every push; the database directory must be /data');
});

test('the container does not run as root', () => {
  assert.match(dockerfile, /^USER node$/m);
});
