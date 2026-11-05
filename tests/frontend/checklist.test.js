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

const filterStatus = () => document.getElementById('filter-status').textContent;
const shown = () => pieces().map(piece => !piece.classList.contains('filtered-out'));

test('the part filter matches number, name and colour, ignoring case', () => {
  window.filter_pieces('3002');
  assert.deepEqual(shown(), [false, false, true]);
  assert.equal(filterStatus(), '1 of 3 parts match');

  window.filter_pieces('RED');
  assert.deepEqual(shown(), [true, false, true]);

  window.filter_pieces('  red   3001 ');
  assert.deepEqual(shown(), [true, false, false]);

  window.filter_pieces('trans-dark brick');
  assert.deepEqual(shown(), [false, true, false]);
});

test('clearing the filter shows every part again', () => {
  window.filter_pieces('nothing like this');
  assert.deepEqual(shown(), [false, false, false]);
  assert.equal(filterStatus(), '0 of 3 parts match');
  window.filter_pieces('');
  assert.deepEqual(shown(), [true, true, true]);
  assert.equal(filterStatus(), '');
});

function readBlob(blob) {
  return new Promise((resolve, reject) => {
    const reader = new window.FileReader();
    reader.onload = () => resolve(reader.result);
    reader.onerror = reject;
    reader.readAsText(blob);
  });
}

async function exportedFile() {
  let saved;
  window.URL.createObjectURL = blob => { saved = blob; return 'blob:test'; };
  window.URL.revokeObjectURL = () => {};
  window.export_progress();
  return JSON.parse(await readBlob(saved));
}

test('saving progress writes every set\'s ticks and nothing else', async () => {
  setChecked(boxes()[0], true);
  window.localStorage.setItem('brick:other-1:3001:Blue:1', 'true');
  window.localStorage.setItem('legochecklist-view', 'list');

  const data = await exportedFile();

  assert.equal(data.format, 'legochecklist-progress');
  assert.equal(data.version, 1);
  assert.deepEqual(data.ticks, ['1-1:3001:Red:1', 'other-1:3001:Blue:1']);
  assert.equal(document.getElementById('progressfile-status').textContent, 'Saved 2 ticks.');
});

test('the saved file is named after the set', () => {
  let downloadedAs;
  window.URL.createObjectURL = () => 'blob:test';
  window.URL.revokeObjectURL = () => {};
  window.HTMLAnchorElement.prototype.click = function () { downloadedAs = this.download; };

  document.querySelector('[data-set-id]').click();

  assert.equal(downloadedAs, 'legochecklist-progress-1-1.json');
});

test('set IDs are made safe for filenames', () => {
  assert.equal(window.progress_filename('1224.1-1'), 'legochecklist-progress-1224.1-1.json');
  assert.equal(window.progress_filename('a/b\\c:d e'), 'legochecklist-progress-a_b_c_d_e.json');
  assert.equal(window.progress_filename(''), 'legochecklist-progress.json');
});

test('a saved file restores ticks in a fresh browser', async () => {
  setChecked(boxes()[0], true);
  setChecked(boxes()[4], true);
  const data = await exportedFile();

  window.localStorage.clear();
  reloadSavedState();
  assert.equal(progress(), '0 / 5 found');

  assert.equal(window.import_progress(JSON.stringify(data)), 2);
  assert.deepEqual(boxes().map(box => box.checked), [true, false, false, false, true]);
  assert.equal(progress(), '2 / 5 found');
});

test('loading progress replaces the current ticks for every set', () => {
  setChecked(boxes()[1], true);
  setChecked(boxes()[3], true);
  window.localStorage.setItem('brick:other-1:3001:Blue:1', 'true');
  window.localStorage.setItem('legochecklist-view', 'list');

  window.import_progress(JSON.stringify({
    format: 'legochecklist-progress', version: 1, ticks: ['1-1:3001:Red:1'],
  }));

  assert.deepEqual(boxes().map(box => box.checked), [true, false, false, false, false]);
  assert.equal(progress(), '1 / 5 found');
  assert.deepEqual(
    Object.keys({ ...window.localStorage }).sort(),
    ['brick:1-1:3001:Red:1', 'legochecklist-view'],
  );
});

test('loading progress shows cards that are no longer finished', async () => {
  setChecked(hideOption(), true);
  setChecked(boxes()[4], true);
  await wait(HIDE_ANIMATION_MS);
  assert.equal(pieces()[2].classList.contains('hidden'), true);

  window.import_progress(JSON.stringify({
    format: 'legochecklist-progress', version: 1, ticks: ['1-1:3001:Red:1', '1-1:3001:Red:2'],
  }));
  await wait(HIDE_ANIMATION_MS);

  assert.deepEqual(pieces().map(piece => piece.classList.contains('hidden')), [true, false, false]);
});

async function chooseFile(text, confirmAnswer) {
  const asked = [];
  window.confirm = message => { asked.push(message); return confirmAnswer; };
  const input = document.getElementById('progressfile');
  const file = new window.File([text], 'progress.json', { type: 'application/json' });
  if (!file.text) {
    file.text = () => Promise.resolve(text);
  }
  Object.defineProperty(input, 'files', { value: [file], configurable: true });
  window.load_progress_file(input);
  await wait(50);
  return asked;
}

const fileWithFirstTick = JSON.stringify({
  format: 'legochecklist-progress', version: 1, ticks: ['1-1:3001:Red:1'],
});

test('loading a file asks before replacing existing ticks, and can be cancelled', async () => {
  setChecked(boxes()[3], true);

  const asked = await chooseFile(fileWithFirstTick, false);

  assert.match(asked[0], /Replace your 1 current tick, for every set, with the 1 in this file/);
  assert.deepEqual(boxes().map(box => box.checked), [false, false, false, true, false]);
});

test('loading a file replaces ticks once confirmed', async () => {
  setChecked(boxes()[3], true);

  await chooseFile(fileWithFirstTick, true);

  assert.deepEqual(boxes().map(box => box.checked), [true, false, false, false, false]);
  assert.equal(document.getElementById('progressfile-status').textContent, 'Loaded 1 tick.');
});

test('loading a file without existing ticks does not ask', async () => {
  const asked = await chooseFile(fileWithFirstTick, false);

  assert.deepEqual(asked, []);
  assert.equal(boxes()[0].checked, true);
});

test('loading a file that is not a progress file changes nothing', () => {
  for (const text of ['not json', '{}', '{"format":"other","ticks":["1-1:3001:Red:1"]}']) {
    assert.throws(() => window.import_progress(text));
  }
  assert.equal(boxes().filter(box => box.checked).length, 0);
  assert.deepEqual(Object.keys({ ...window.localStorage }), []);
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
