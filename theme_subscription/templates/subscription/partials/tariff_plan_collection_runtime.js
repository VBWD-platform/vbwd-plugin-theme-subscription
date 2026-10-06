/*
 * tariff_plan_collection_runtime.js — the TariffPlanCollection toolbar (S152-08), ES2019,
 * inlined by the widget (installs once). Mirrors useCollectionView + CollectionToolbar:
 *   - the quick search hides plans whose search text lacks the trimmed, lower-cased query;
 *   - the sort toggle flips the price order (asc ↔ desc) of the cards and table rows;
 *   - the view buttons switch between the cards grid and the table.
 * Everything is delegated on document, so a swapped region keeps working.
 */
(function (window) {
  'use strict';
  if (window.VbwdTariffPlanCollection) {
    return;
  }

  var ROOT_SELECTOR = '.tariff-plan-collection';
  var PLAN_SELECTOR = '[data-vbwd-plan]';
  var LIST_SELECTOR = '[data-vbwd-plan-list]';
  var SEARCH_SELECTOR = '[data-testid="collection-search"]';
  var SORT_SELECTOR = '[data-testid="collection-sort-toggle"]';
  var CARDS_SELECTOR = '[data-testid="collection-view-cards"]';
  var TABLE_SELECTOR = '[data-testid="collection-view-table"]';
  var GRID_SELECTOR = '[data-testid="tariff-plan-grid"]';
  var TABLE_WRAPPER_SELECTOR = '.tariff-plan-collection__table-wrapper';
  var ARROW_SELECTOR = '[data-vbwd-sort-arrow]';
  var DIRECTION_ATTRIBUTE = 'data-sort-direction';
  var ASCENDING = 'asc';
  var DESCENDING = 'desc';
  var ARROWS = { asc: '↑', desc: '↓' };
  var ACTIVE_CLASS = 'active';

  function matchesQuery(searchText, query) {
    var normalized = String(query || '').trim().toLowerCase();
    return normalized === '' || String(searchText || '').indexOf(normalized) !== -1;
  }

  function applySearch(root, query) {
    root.querySelectorAll(PLAN_SELECTOR).forEach(function (plan) {
      plan.hidden = !matchesQuery(plan.getAttribute('data-search-text'), query);
    });
  }

  function applySort(root, direction) {
    root.querySelectorAll(LIST_SELECTOR).forEach(function (list) {
      var plans = Array.prototype.slice.call(list.querySelectorAll(PLAN_SELECTOR));
      plans.sort(function (first, second) {
        var difference = Number(first.getAttribute('data-sort-key')) - Number(second.getAttribute('data-sort-key'));
        return direction === ASCENDING ? difference : -difference;
      });
      plans.forEach(function (plan) {
        list.appendChild(plan);
      });
    });
  }

  function toggleSort(root) {
    var direction = root.getAttribute(DIRECTION_ATTRIBUTE) === ASCENDING ? DESCENDING : ASCENDING;
    root.setAttribute(DIRECTION_ATTRIBUTE, direction);
    root.querySelector(ARROW_SELECTOR).textContent = ARROWS[direction];
    applySort(root, direction);
  }

  function setView(root, showTable) {
    root.querySelector(GRID_SELECTOR).hidden = showTable;
    root.querySelector(TABLE_WRAPPER_SELECTOR).hidden = !showTable;
    root.querySelector(CARDS_SELECTOR).classList.toggle(ACTIVE_CLASS, !showTable);
    root.querySelector(TABLE_SELECTOR).classList.toggle(ACTIVE_CLASS, showTable);
  }

  function handleInput(event) {
    var target = event.target;
    if (!target || !target.closest || !target.matches(SEARCH_SELECTOR)) return;
    applySearch(target.closest(ROOT_SELECTOR), target.value);
  }

  function handleClick(event) {
    var target = event.target;
    if (!target || !target.closest) return;
    var root = target.closest(ROOT_SELECTOR);
    if (!root) return;
    if (target.closest(SORT_SELECTOR)) return toggleSort(root);
    if (target.closest(CARDS_SELECTOR)) return setView(root, false);
    if (target.closest(TABLE_SELECTOR)) return setView(root, true);
  }

  window.document.addEventListener('input', handleInput);
  window.document.addEventListener('click', handleClick);

  window.VbwdTariffPlanCollection = Object.freeze({ matchesQuery: matchesQuery });
})(window);
