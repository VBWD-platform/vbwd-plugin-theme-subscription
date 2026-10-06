// S152-08 — the TariffPlanCollection toolbar's client-only rules (node --test).
// DRIFT NOTE — mirrored from:
//   matchesQuery / sortedKeys — vbwd-fe-user vue/src/composables/useCollectionView.ts
//   toolbar events            — vbwd-fe-user vue/src/components/CollectionToolbar.vue
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import vm from 'node:vm';

const RUNTIME_PATH = fileURLToPath(
  new URL(
    '../../theme_subscription/templates/subscription/partials/tariff_plan_collection_runtime.js',
    import.meta.url,
  ),
);

function loadRuntime() {
  const listeners = {};
  const context = {
    document: {
      addEventListener: (type, listener) => (listeners[type] = listeners[type] || []).push(listener),
    },
  };
  context.window = context;
  vm.createContext(context);
  const source = readFileSync(RUNTIME_PATH, 'utf8');
  vm.runInContext(source, context);
  vm.runInContext(source, context); // included once per widget: must install once
  return { runtime: context.VbwdTariffPlanCollection, listeners };
}

function element(attributes = {}, children = []) {
  const node = {
    attributes: { ...attributes },
    children,
    hidden: false,
    textContent: '',
    classList: {
      names: new Set((attributes.class || '').split(' ').filter(Boolean)),
      toggle(name, on) {
        if (on) this.names.add(name);
        else this.names.delete(name);
      },
    },
    getAttribute: (name) => (name in node.attributes ? node.attributes[name] : null),
    setAttribute: (name, value) => (node.attributes[name] = String(value)),
    appendChild: (child) => {
      node.children = node.children.filter((existing) => existing !== child).concat(child);
    },
    querySelector: (selector) => node.querySelectorAll(selector)[0] || null,
    querySelectorAll: (selector) => {
      const found = [];
      const visit = (current) => {
        current.children.forEach((child) => {
          if (child.matches(selector)) found.push(child);
          visit(child);
        });
      };
      visit(node);
      return found;
    },
    matches: (selector) => {
      const attribute = selector.match(/^\[([\w-]+)(?:="([^"]*)")?\]$/);
      if (attribute) {
        return attribute[2] === undefined
          ? attribute[1] in node.attributes
          : node.attributes[attribute[1]] === attribute[2];
      }
      return selector.startsWith('.') && node.classList.names.has(selector.slice(1));
    },
    closest: (selector) => {
      let current = node;
      while (current) {
        if (current.matches(selector)) return current;
        current = current.parent;
      }
      return null;
    },
  };
  children.forEach((child) => (child.parent = node));
  return node;
}

function plan(slug, searchText, sortKey) {
  return element({ 'data-vbwd-plan': slug, 'data-search-text': searchText, 'data-sort-key': String(sortKey) });
}

function collection() {
  const arrow = element({ 'data-vbwd-sort-arrow': '' });
  const sortToggle = element({ 'data-testid': 'collection-sort-toggle' }, [arrow]);
  const search = element({ 'data-testid': 'collection-search' });
  const cardsButton = element({ 'data-testid': 'collection-view-cards', class: 'collection-toolbar__view-btn active' });
  const tableButton = element({ 'data-testid': 'collection-view-table', class: 'collection-toolbar__view-btn' });
  const grid = element({ 'data-testid': 'tariff-plan-grid', 'data-vbwd-plan-list': '' }, [
    plan('basic', 'basic starter', 9),
    plan('pro', 'pro teams', 29),
  ]);
  const tbody = element({ 'data-vbwd-plan-list': '' }, [plan('basic', 'basic starter', 9), plan('pro', 'pro teams', 29)]);
  const tableWrapper = element({ class: 'tariff-plan-collection__table-wrapper' }, [tbody]);
  tableWrapper.hidden = true;
  const root = element({ class: 'tariff-plan-collection', 'data-sort-direction': 'asc' }, [
    search,
    sortToggle,
    cardsButton,
    tableButton,
    grid,
    tableWrapper,
  ]);
  return { root, search, sortToggle, arrow, cardsButton, tableButton, grid, tbody, tableWrapper };
}

const slugs = (list) => list.children.map((child) => child.getAttribute('data-vbwd-plan'));
const visibleSlugs = (list) =>
  list.children.filter((child) => !child.hidden).map((child) => child.getAttribute('data-vbwd-plan'));

test('installs once even when the partial is included several times', () => {
  const { listeners } = loadRuntime();

  assert.equal(listeners.input.length, 1);
  assert.equal(listeners.click.length, 1);
});

test('the quick search is a trimmed, case-insensitive substring match', () => {
  const { runtime } = loadRuntime();

  assert.equal(runtime.matchesQuery('pro teams', '  TEAM '), true);
  assert.equal(runtime.matchesQuery('pro teams', 'basic'), false);
  assert.equal(runtime.matchesQuery('anything', '   '), true);
});

test('typing in the search hides the plans that do not match, in both views', () => {
  const { listeners } = loadRuntime();
  const parts = collection();
  parts.search.value = 'TEAMS';

  listeners.input[0]({ target: parts.search });

  assert.deepEqual(visibleSlugs(parts.grid), ['pro']);
  assert.deepEqual(visibleSlugs(parts.tbody), ['pro']);
});

test('the sort toggle flips the price order and the arrow', () => {
  const { listeners } = loadRuntime();
  const parts = collection();

  listeners.click[0]({ target: parts.arrow });

  assert.deepEqual(slugs(parts.grid), ['pro', 'basic']);
  assert.deepEqual(slugs(parts.tbody), ['pro', 'basic']);
  assert.equal(parts.arrow.textContent, '↓');
  assert.equal(parts.root.getAttribute('data-sort-direction'), 'desc');

  listeners.click[0]({ target: parts.sortToggle });

  assert.deepEqual(slugs(parts.grid), ['basic', 'pro']);
  assert.equal(parts.arrow.textContent, '↑');
});

test('the view buttons switch between cards and table', () => {
  const { listeners } = loadRuntime();
  const parts = collection();

  listeners.click[0]({ target: parts.tableButton });

  assert.equal(parts.grid.hidden, true);
  assert.equal(parts.tableWrapper.hidden, false);
  assert.equal(parts.tableButton.classList.names.has('active'), true);
  assert.equal(parts.cardsButton.classList.names.has('active'), false);

  listeners.click[0]({ target: parts.cardsButton });

  assert.equal(parts.grid.hidden, false);
  assert.equal(parts.tableWrapper.hidden, true);
});
