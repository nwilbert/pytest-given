// --- The delta page ---
// The report's Alpine component with a Change filter beside the Status one.
// Loaded after app.js, whose helpers it reuses; `__REPORT_DATA__` here holds
// one entry per listed scenario, keyed by its slug, since a removed and an
// added scenario can share a node ID.
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
  const overrides = {
    shownChanges: allChangesShown(),
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
    goToTerm(id) {
      if (hasTerms()) base.goToTerm.call(this, id);
    },
    init() {
      base.init.call(this);
      this.$watch('shownChanges', () => { if (!this._suppressHashWrite) this._writeHash('push'); });
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
