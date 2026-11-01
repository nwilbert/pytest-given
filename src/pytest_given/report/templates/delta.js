// --- The delta page ---
// The report's Alpine component with a Change filter beside the Status one,
// on each tab. Loaded after app.js, whose helpers it reuses;
// `__REPORT_DATA__` here holds one entry per listed scenario, keyed by its
// slug, since a removed and an added scenario can share a node ID, and one
// per term card, keyed likewise.
const CHANGES = ['added', 'changed', 'removed'];

function deltaApp() {
  const data = window.__REPORT_DATA__;
  const base = reportApp();
  const allChangesShown = () => Object.fromEntries(CHANGES.map(c => [c, true]));
  const changeCounts = Object.fromEntries(CHANGES.map(c => [c, 0]));
  for (const s of data.scenarios) changeCounts[s.change] += 1;
  const changesPresent = CHANGES.filter(c => changeCounts[c] > 0);
  const moduleChanges = data.module_changes || {};
  // The before glossary's terms that read otherwise than the after one's.
  const beforeTerms = new Map((data.before_terms || []).map(t => [t.id, t]));
  const termCards = data.term_cards || [];
  const cardKeys = new Set(termCards.map(card => card.key));
  // A term ref's card, by the side the ref was read on and its term id.
  const cardOf = { before: {}, after: {} };
  for (const card of termCards) {
    for (const side of ['before', 'after']) if (card[side]) cardOf[side][card[side]] = card.key;
  }
  const overrides = {
    shownChanges: allChangesShown(),
    // The Glossary tab's own, as its search is: not in the URL.
    shownTermChanges: allChangesShown(),
    get changeCounts() {
      return changeCounts;
    },
    moduleChange(module) {
      return lookup(moduleChanges, module, null);
    },
    changeGlyph(change) {
      return data.change_glyphs[change];
    },
    _filterState() {
      return [...base._filterState.call(this), ...CHANGES.map(c => this.shownChanges[c])];
    },
    _matchesFilters(s, index, query) {
      return this.shownChanges[s.change] && base._matchesFilters.call(this, s, index, query);
    },
    _summaryParts() {
      const shown = changesPresent.filter(c => this.shownChanges[c]);
      const parts = base._summaryParts.call(this);
      if (shown.length === changesPresent.length) return parts;
      return [shown.length ? shown.join(', ') : 'no changes', ...parts];
    },
    // Unfiltered, the header breaks the count down by change.
    get filterSummary() {
      const parts = this._summaryParts();
      if (parts.length) return parts.join(' ');
      if (this._chipped()) return '';
      return changesPresent.map(c => changeCounts[c] + ' ' + c).join(', ');
    },
    resetFilters() {
      base.resetFilters.call(this);
      this.shownChanges = allChangesShown();
    },
    // A ref inside `data-term-side="before"` was read against the before
    // glossary; every other against the after one.
    _tipTerm(pill) {
      const before = pill.closest('[data-term-side="before"]') && beforeTerms.get(pill.dataset.termId);
      return before || base._tipTerm.call(this, pill);
    },
    // The Glossary tab lists only the terms that changed; a term ref to any
    // other has nowhere to go.
    _hasTermEntry(key) {
      return cardKeys.has(key);
    },
    _refEntry(pill) {
      const side = pill.closest('[data-term-side="before"]') ? 'before' : 'after';
      return lookup(cardOf[side], pill.dataset.termId, null);
    },
    // Over the cards, which the Change filter narrows too, rather than over a
    // glossary's terms.
    _termCounts() {
      const query = this.glossarySearch.toLowerCase();
      const definitions = this.glossaryDefinitionFilter;
      const counts = {};
      for (const card of termCards) {
        if (!this.shownTermChanges[card.change]) continue;
        if (definitions !== 'all' && (definitions === 'defined') !== card.defined) continue;
        if (query && !card.search.includes(query)) continue;
        counts[card.kind] = (counts[card.kind] || 0) + 1;
      }
      return counts;
    },
    // A side's table previews into its own side's text; the one table of a
    // scenario whose table didn't change, into both.
    _previewSpans(rowEl, scope) {
      const spans = base._previewSpans.call(this, rowEl, scope);
      const side = rowEl.closest('[data-side]')?.dataset.side;
      if (!side) return spans;
      return spans.filter(span => span.closest('[data-side]')?.dataset.side === side);
    },
    init() {
      base.init.call(this);
      this.$watch('shownChanges', () => { if (!this._suppressHashWrite) this._writeHash('push'); });
      this._initAlignment();
    },
    // Side by side, a step and a case each keep one line across both sides.
    // Re-aligned whenever a side resizes (sub-steps or a payload opened, the
    // window narrowed), in the next frame: resizing an observed element
    // inside its own callback would loop.
    _initAlignment() {
      for (const sides of document.querySelectorAll('.delta-sides')) {
        const steps = sides.querySelectorAll(':scope > .delta-side-steps');
        const tables = sides.querySelectorAll(':scope > .delta-table .param-table');
        if (steps.length === 2) alignOnResize(steps, () => alignRows(...steps));
        if (tables.length === 2) alignOnResize(tables, () => alignBands(...tables));
      }
    },
    _readHash() {
      base._readHash.call(this);
      const params = parseHash();
      if (params.has('change')) {
        const shown = new Set(params.get('change').split(','));
        this.shownChanges = Object.fromEntries(CHANGES.map(c => [c, shown.has(c)]));
      } else {
        this.shownChanges = allChangesShown();
      }
    },
    _hashParams() {
      const params = base._hashParams.call(this);
      const shown = changesPresent.filter(c => this.shownChanges[c]);
      if (shown.length !== changesPresent.length) params.set('change', shown.join(','));
      return params;
    },
  };
  // Copied by descriptor rather than spread: a spread would read every getter
  // once, here, and keep its value instead of the getter.
  const app = Object.defineProperties({},Object.getOwnPropertyDescriptors(base));
  return Object.defineProperties(app, Object.getOwnPropertyDescriptors(overrides));
}

function alignOnResize(elements, align) {
  let queued = false;
  const observer = new ResizeObserver(() => {
    if (queued) return;
    queued = true;
    requestAnimationFrame(() => {
      queued = false;
      align();
    });
  });
  elements.forEach(element => observer.observe(element));
}

// Each row's line starts level on both sides, the higher one pushed down, and
// a hatched gap is as tall as the step it stands in for. Every position is
// read before any is written: a push moves every line below it on its side
// by as much, which the running shift accounts for. Rows inside closed
// sub-steps take no room and are left out, alike on both sides.
function alignRows(before, after) {
  if (!before.getClientRects().length) return;  // a hidden scenario
  const shown = side => [...side.querySelectorAll('[data-row]')]
    .filter(row => !row.parentElement.closest('.step-expand:not(.expanded)'));
  const pairs = zip(shown(before), shown(after));
  if (!pairs) {
    console.assert(false, 'delta steps have unequal rows', before, after);
    return;
  }
  for (const row of pairs.flat()) {
    row.style.paddingTop = '';
    row.style.height = '';
  }
  const boxes = pairs.map(pair => pair.map(row => row.getBoundingClientRect()));
  const shift = [0, 0];
  pairs.forEach((pair, i) => {
    const tops = boxes[i].map((box, side) => box.top + shift[side]);
    const level = Math.max(...tops);
    pair.forEach((row, side) => {
      const push = level - tops[side] >= 0.5 ? level - tops[side] : 0;
      if (push) row.style.paddingTop = `${push}px`;
      shift[side] += push;
      if (!row.classList.contains('delta-gap')) return;
      // Box-sized: the gap's height holds its push.
      const height = boxes[i][1 - side].height;
      row.style.height = `${push + height}px`;
      shift[side] += height - boxes[i][side].height;
    });
  });
}

// The two sides' rows by position, each pair the same row; null when they
// don't pair up.
function zip(before, after) {
  if (before.length !== after.length) return null;
  if (before.some((row, i) => row.dataset.row !== after[i].dataset.row)) return null;
  return before.map((row, i) => [row, after[i]]);
}

// Each band (the header, or a case with its error and payload rows) grows its
// last row on the shorter side by the difference. Every height is read before
// any is written, so the tables lay out once.
function alignBands(before, after) {
  const beforeBands = before.querySelectorAll('[data-band]');
  const afterBands = after.querySelectorAll('[data-band]');
  // The template gives both tables a band per row; anything else can't be paired.
  if (beforeBands.length !== afterBands.length) {
    console.assert(false, 'delta tables have unequal bands', before, after);
    return;
  }
  const pairs = [...beforeBands].map((band, i) => [band, afterBands[i]]);
  const lastRows = pairs.map(pair => pair.map(band => band.rows[band.rows.length - 1]));
  for (const row of lastRows.flat()) row.style.height = '';
  const bandHeights = pairs.map(pair => pair.map(band => band.getBoundingClientRect().height));
  const rowHeights = lastRows.map(rows => rows.map(row => row.getBoundingClientRect().height));
  bandHeights.forEach(([beforeHeight, afterHeight], i) => {
    const gap = Math.abs(beforeHeight - afterHeight);
    if (gap < 0.5) return;
    const shorter = beforeHeight < afterHeight ? 0 : 1;
    lastRows[i][shorter].style.height = `${rowHeights[i][shorter] + gap}px`;
  });
}
