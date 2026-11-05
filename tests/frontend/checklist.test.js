// Loads the page from render_fixture.py and exercises its inline script.
// Parts, in order: 3001 Red x2, 3001 Trans-Dark Blue x2, 3002 Red x1.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const { beforeEach, test } = require('node:test');
const { setTimeout: wait } = require('node:timers/promises');
const { JSDOM, VirtualConsole } = require('jsdom');

const html = fs.readFileSync(path.join(__dirname, 'rendered.html'), 'utf8');
const HIDE_ANIMATION_MS = 400;

let window, document, errors;

const boxes = () => Array.from(document.querySelectorAll('.piece input[type="checkbox"]'));
const pieces = () => Array.from(document.querySelectorAll('.piece'));
const hideOption = () => document.getElementById('hideondone');
const progress = () => document.getElementById('progress').textContent;

function setChecked(checkbox, checked) {
  checkbox.checked = checked;
  checkbox.dispatchEvent(new window.Event('change'));
}

function reloadSavedState() {
  boxes().forEach(box => { box.checked = false; });
  hideOption().checked = false;
  window.start();
}

beforeEach(() => {
  errors = [];
  const virtualConsole = new VirtualConsole();
  virtualConsole.on('jsdomError', error => errors.push(error.detail?.message ?? error.message));
  ({ window } = new JSDOM(html, {
    runScripts: 'dangerously',
    url: 'http://localhost/',
    virtualConsole,
  }));
  document = window.document;
  window.start();
});

test('ticking one box restores only that box', () => {
  setChecked(boxes()[0], true);
  reloadSavedState();
  assert.deepEqual(boxes().map(box => box.checked), [true, false, false, false, false]);
  assert.deepEqual(errors, []);
});

test('saved state is specific to the set', () => {
  setChecked(boxes()[0], true);
  assert.deepEqual(Object.keys({ ...window.localStorage }), ['brick:1-1:3001:Red:1']);
});

test('turning on hide does not throw and leaves unfinished cards', () => {
  setChecked(boxes()[0], true);
  setChecked(hideOption(), true);
  assert.deepEqual(errors, []);
  assert.equal(document.querySelectorAll('.hiding').length, 0);
});

test('finishing a part hides its whole card and nothing else', async () => {
  setChecked(hideOption(), true);
  setChecked(boxes()[0], true);
  setChecked(boxes()[1], true);
  await wait(HIDE_ANIMATION_MS);
  assert.deepEqual(pieces().map(piece => piece.classList.contains('hidden')), [true, false, false]);
});

test('the hide option survives a reload', () => {
  setChecked(hideOption(), true);
  reloadSavedState();
  assert.equal(hideOption().checked, true);
});

test('turning hide off mid-animation leaves the card visible', async () => {
  setChecked(hideOption(), true);
  setChecked(boxes()[4], true);
  setChecked(hideOption(), false);
  await wait(HIDE_ANIMATION_MS);
  assert.equal(document.querySelectorAll('.hidden').length, 0);
});

test('reset clears saved boxes, shows cards and keeps the hide option', async () => {
  setChecked(hideOption(), true);
  setChecked(boxes()[4], true);
  await wait(HIDE_ANIMATION_MS);
  window.reset();
  assert.equal(boxes().filter(box => box.checked).length, 0);
  assert.equal(document.querySelectorAll('.hidden, .hiding').length, 0);
  assert.equal(hideOption().checked, true);
  assert.deepEqual(
    Object.keys({ ...window.localStorage }).filter(key => key.startsWith('brick:')),
    [],
  );
});

const viewButton = () => document.getElementById('viewtoggle');
const inListView = () => document.body.classList.contains('list-view');

test('the page starts in tile view', () => {
  assert.equal(inListView(), false);
  assert.equal(viewButton().textContent, 'List view');
  assert.equal(viewButton().getAttribute('aria-pressed'), 'false');
});

test('the view button switches between list and tile views', () => {
  viewButton().click();
  assert.equal(inListView(), true);
  assert.equal(viewButton().textContent, 'Tile view');
  assert.equal(viewButton().getAttribute('aria-pressed'), 'true');
  viewButton().click();
  assert.equal(inListView(), false);
  assert.equal(viewButton().textContent, 'List view');
  assert.deepEqual(errors, []);
});

test('the chosen view survives a reload and does not touch ticks', () => {
  setChecked(boxes()[0], true);
  viewButton().click();
  document.body.classList.remove('list-view');
  reloadSavedState();
  assert.equal(inListView(), true);
  assert.equal(viewButton().textContent, 'Tile view');
  assert.deepEqual(boxes().map(box => box.checked), [true, false, false, false, false]);
});

test('progress follows ticks, reloads and reset', () => {
  assert.equal(progress(), '0 / 5 found');
  setChecked(boxes()[0], true);
  setChecked(boxes()[3], true);
  assert.equal(progress(), '2 / 5 found');
  reloadSavedState();
  assert.equal(progress(), '2 / 5 found');
  window.reset();
  assert.equal(progress(), '0 / 5 found');
});
