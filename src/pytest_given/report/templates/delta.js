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
    // A phase block narrates the after table's columns. A lone before table
    // has none it narrates.
    _phaseTable(scope) {
      if (!scope.querySelector('.delta-tables')) return base._phaseTable.call(this, scope);
      return scope.querySelector('.delta-table[data-side="after"] .param-table');
    },
    init() {
      base.init.call(this);
      this.$watch('shownChanges', () => { if (!this._suppressHashWrite) this._writeHash('push'); });
      this._initTableAlignment();
    },
    // Side by side, a case keeps one line across both tables. Re-aligned
    // whenever a table resizes (a payload opened, the window narrowed), in
    // the next frame: resizing an observed element inside its own callback
    // would loop.
    _initTableAlignment() {
      for (const pair of document.querySelectorAll('.delta-tables')) {
        const tables = pair.querySelectorAll('.param-table');
        if (tables.length !== 2) continue;
        let queued = false;
        const observer = new ResizeObserver(() => {
          if (queued) return;
          queued = true;
          requestAnimationFrame(() => {
            queued = false;
            alignBands(...tables);
          });
        });
        tables.forEach(table => observer.observe(table));
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
