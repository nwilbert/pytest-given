// --- Hash helpers ---
function parseHash() {
  return new URLSearchParams(window.location.hash.slice(1));
}

function serializeHash(params, mode = 'push') {
  const qs = params.toString();
  const newHash = qs ? '#' + qs : '';
  // No-op when the hash is unchanged: avoids spurious history entries and
  // breaks the readHash -> watcher -> writeHash feedback loop.
  if (newHash === window.location.hash) return;
  const url = qs ? '#' + qs : window.location.pathname + window.location.search;
  if (mode === 'replace') history.replaceState(null, '', url);
  else history.pushState(null, '', url);
}

function deserializeView(params) {
  const v = params.get('view');
  if (v === 'stories' || v === 'glossary') return v;
  return 'scenarios';
}

function deserializeStory(params) {
  const s = params.get('story');
  const ids = window.__storyIds || [];
  return (s && ids.includes(s)) ? s : (ids[0] || null);
}

// --- Alpine app ---
function reportApp() {
  const data = window.__REPORT_DATA__;
  const storyIds = window.__storyIds || [];
  return {
    search: '',
    view: 'tags',
    mainView: 'scenarios',
    selectedStory: storyIds[0] || null,
    glossarySearch: '',
    glossaryKindFilter: { actor: true, object: true, verb: true, kindless: true },
    expandedTerms: {},
    hoveredActivity: null,
    hoveredScenario: null,
    showPassed: true,
    showFailed: true,
    showSkipped: true,
    expandedGroups: {},
    expandedSteps: {},
    expandedAttachments: {},
    expandedScenarios: {},
    activeTag: null,
    termFilter: null,
    _suppressHashWrite: false,
    highlightedActivities: {},
    get anyActivitiesHighlighted() {
      return Object.keys(this.highlightedActivities).length > 0;
    },
    toggleActivityHighlight(id) {
      if (this.highlightedActivities[id]) delete this.highlightedActivities[id];
      else this.highlightedActivities[id] = true;
    },
    clearActivityHighlights() {
      this.highlightedActivities = {};
    },
    // Story-view scenario cards filter on the selected activities: a card stays
    // visible when nothing is selected, or when it covers ANY selected activity.
    activitySelectionMatches(coveredIds) {
      if (!this.anyActivitiesHighlighted) return true;
      return coveredIds.some(id => this.highlightedActivities[id]);
    },
    get anyTermsExpanded() {
      return Object.keys(this.expandedTerms).length > 0;
    },
    toggleAllTerms() {
      const expand = !this.anyTermsExpanded;
      const ids = window.__termIds || [];
      if (expand) {
        ids.forEach(id => { this.expandedTerms[id] = true; });
      } else {
        this.expandedTerms = {};
      }
    },
    get filterSummary() {
      const parts = [];
      if (this.activeTag) parts.push('Tag: ' + this.activeTag);
      const hasStatus = (s) => data.scenarios.some(sc => sc.status === s);
      const allShown = (this.showPassed || !hasStatus('passed'))
        && (this.showFailed || !hasStatus('failed'))
        && (this.showSkipped || !hasStatus('skipped'));
      if (!allShown) {
        const shown = [];
        if (this.showPassed && hasStatus('passed')) shown.push('passed');
        if (this.showFailed && hasStatus('failed')) shown.push('failed');
        if (this.showSkipped && hasStatus('skipped')) shown.push('skipped');
        if (shown.length) parts.push(shown.join(', '));
      }
      if (this.search) parts.push('"' + this.search + '"');
      // The term filter is shown as its own removable chip, so it isn't
      // repeated here; suppress the "All Scenarios" fallback while it's active.
      if (parts.length) return parts.join(' · ');
      return this.termFilter ? '' : 'All Scenarios';
    },
    get formattedTimestamp() {
      const d = new Date(data.metadata.timestamp);
      if (isNaN(d)) return data.metadata.timestamp;
      return d.toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' })
        + ' at ' + d.toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit', hour12: false });
    },
    get counts() {
      return {
        passed: data.scenarios.filter(s => s.status === 'passed').length,
        failed: data.scenarios.filter(s => s.status === 'failed').length,
        skipped: data.scenarios.filter(s => s.status === 'skipped').length,
      };
    },
    get filteredCount() {
      return data.scenarios.filter((_, i) => this.isVisible(i)).length;
    },
    get groups() {
      const grouped = {};
      for (const s of data.scenarios) {
        if (!this._matchesFilters(s)) continue;
        const keys = this.view === 'tags'
          ? (s.tags.length ? s.tags : ['untagged'])
          : [s.module];
        for (const k of keys) {
          if (!grouped[k]) grouped[k] = { name: k, scenarios: [] };
          grouped[k].scenarios.push(s);
        }
      }
      return Object.values(grouped).sort((a, b) => a.name.localeCompare(b.name));
    },
    _matchesFilters(s) {
      if (s.status === 'passed' && !this.showPassed) return false;
      if (s.status === 'failed' && !this.showFailed) return false;
      if (s.status === 'skipped' && !this.showSkipped) return false;
      if (this.activeTag && !s.tags.includes(this.activeTag)) return false;
      if (this.termFilter &&
          !(window.__termScenarios[this.termFilter] || []).includes(s.id)) {
        return false;
      }
      if (this.search) {
        const q = this.search.toLowerCase();
        const text = (s.narration.text + ' ' + s.tags.join(' ')).toLowerCase();
        if (!text.includes(q)) return false;
      }
      return true;
    },
    toggleGroup(name) {
      if (this.expandedGroups[name]) delete this.expandedGroups[name];
      else this.expandedGroups[name] = true;
    },
    toggleStep(stepId) {
      if (this.expandedSteps[stepId]) delete this.expandedSteps[stepId];
      else this.expandedSteps[stepId] = true;
    },
    toggleScenario(index) {
      if (this.expandedScenarios[index]) delete this.expandedScenarios[index];
      else this.expandedScenarios[index] = true;
    },
    get anyScenariosExpanded() {
      return data.scenarios.some((_, i) => this.isVisible(i) && this.expandedScenarios[i]);
    },
    toggleAllScenarios() {
      const expand = !this.anyScenariosExpanded;
      data.scenarios.forEach((_, i) => {
        if (this.isVisible(i)) {
          if (expand) this.expandedScenarios[i] = true;
          else delete this.expandedScenarios[i];
        }
      });
    },
    isVisible(index) {
      const scenario = data.scenarios[index];
      if (!scenario) return false;
      return this._matchesFilters(scenario);
    },
    scrollToAndExpand(id) {
      const index = data.scenarios.findIndex(s => s.id === id);
      if (index === -1) return;
      this.expandedScenarios[index] = true;
      this.$nextTick(() => {
        const el = document.getElementById('scenario-' + index);
        if (el) el.scrollIntoView({ behavior: 'smooth', block: 'start' });
      });
    },
    goToScenario(nodeId) {
      this.mainView = 'scenarios';
      this.$nextTick(() => this.scrollToAndExpand(nodeId));
    },
    goToTerm(id) {
      this.mainView = 'glossary';
      this.expandedTerms[id] = true;
      this.$nextTick(() => {
        const el = document.getElementById('term-' + id);
        if (el) el.scrollIntoView({ behavior: 'smooth', block: 'start' });
      });
    },
    filterScenariosByTerm(id) {
      this.termFilter = id;
      this.mainView = 'scenarios';
    },
    clearTermFilter() {
      this.termFilter = null;
    },
    filterByTag(tag) {
      if (this.activeTag === tag) {
        this.activeTag = null;
      } else {
        this.activeTag = tag;
        this.view = 'tags';
      }
    },
    toggleAttachment(key) {
      if (this.expandedAttachments[key]) delete this.expandedAttachments[key];
      else this.expandedAttachments[key] = true;
    },
    copyAnchor(hashString, event) {
      history.replaceState(null, '', '#' + hashString);
      if (navigator.clipboard) navigator.clipboard.writeText(window.location.href);
      const btn = event.currentTarget;
      btn.classList.add('anchor-copied');
      setTimeout(() => btn.classList.remove('anchor-copied'), 1200);
    },
    setHoverParam(name, el) {
      const scope = el?.closest('.scenario') || document;
      scope.querySelectorAll('.param-highlight').forEach(e => e.classList.remove('param-highlight'));
      if (!name) return;
      const safe = CSS.escape(name);
      scope.querySelectorAll(
        `th[data-param="${safe}"], td[data-param="${safe}"], span[data-param="${safe}"]`,
      ).forEach(e => e.classList.add('param-highlight'));
    },
    init() {
      this._readHash();
      // Search typing replaces the current entry (no per-keystroke history
      // spam); discrete navigations/filters push a back-able entry. All writes
      // are suppressed while we're applying state FROM the hash (see _readHash).
      this.$watch('search', () => { if (!this._suppressHashWrite) this._writeHash('replace'); });
      ['activeTag', 'termFilter', 'showPassed', 'showFailed', 'showSkipped'].forEach(key => {
        this.$watch(key, () => { if (!this._suppressHashWrite) this._writeHash('push'); });
      });
      this.$watch('mainView', () => { if (!this._suppressHashWrite) this._writeHash('push'); });
      this.$watch('selectedStory', () => { if (!this._suppressHashWrite) this._writeHash('push'); });
      this.$watch('selectedStory', () => { this.highlightedActivities = {}; });
      // hashchange: manual URL edits / pasted links. popstate: back/forward.
      window.addEventListener('hashchange', () => this._readHash());
      window.addEventListener('popstate', () => this._readHash());
      // Capture phase + stopPropagation so a term pill inside a clickable
      // container (e.g. a scenario header) navigates without also triggering
      // that container's click (scenario expand/collapse).
      document.addEventListener('click', (event) => {
        const pill = event.target.closest('[data-term-id]');
        if (!pill) return;
        if (pill.closest('.entry')) return;  // don't self-jump inside a glossary entry
        event.stopPropagation();
        this.goToTerm(pill.dataset.termId);
      }, true);
      document.addEventListener('click', (event) => {
        const chip = event.target.closest('[data-activity-id]');
        if (!chip) return;
        this.toggleActivityHighlight(chip.dataset.activityId);
      });
    },
    _readHash() {
      // Applying state from the hash must not itself write the hash (which
      // would create bogus history entries on back/forward).
      this._suppressHashWrite = true;
      const params = parseHash();
      if (params.has('tag')) this.activeTag = params.get('tag');
      else this.activeTag = null;
      if (params.has('term-filter')) this.termFilter = params.get('term-filter');
      else this.termFilter = null;
      if (params.has('status')) {
        const shown = new Set(params.get('status').split(',').filter(Boolean));
        this.showPassed = shown.has('passed');
        this.showFailed = shown.has('failed');
        this.showSkipped = shown.has('skipped');
      } else {
        this.showPassed = true;
        this.showFailed = true;
        this.showSkipped = true;
      }
      if (params.has('q')) this.search = params.get('q');
      else this.search = '';
      this.mainView = deserializeView(params);
      this.selectedStory = deserializeStory(params);
      const targetSlug = params.get('scenario');
      const targetScenario = targetSlug
        ? (window.__scenarioSlugs || {})[targetSlug]
        : null;
      const targetTerm = params.get('term');
      if (targetTerm) {
        this.goToTerm(targetTerm);
      } else if (targetScenario) {
        this.goToScenario(targetScenario);
      }
      this.$nextTick(() => {
        this._suppressHashWrite = false;
        // Drop one-shot target params (scenario=/term=) without adding history.
        if (targetSlug || targetTerm) this._writeHash('replace');
      });
    },
    _writeHash(mode = 'push') {
      const params = new URLSearchParams();
      if (this.mainView !== 'scenarios') params.set('view', this.mainView);
      if (this.mainView === 'stories' && this.selectedStory) params.set('story', this.selectedStory);
      if (this.activeTag) params.set('tag', this.activeTag);
      if (this.termFilter) params.set('term-filter', this.termFilter);

      const present = new Set(data.scenarios.map(s => s.status));
      const shown = [];
      if (this.showPassed) shown.push('passed');
      if (this.showFailed) shown.push('failed');
      if (this.showSkipped) shown.push('skipped');
      const shownInReport = shown.filter(s => present.has(s));
      const presentList = ['passed', 'failed', 'skipped'].filter(s => present.has(s));
      if (shownInReport.length !== presentList.length) {
        params.set('status', shownInReport.join(','));
      }

      if (this.search) params.set('q', this.search);
      serializeHash(params, mode);
    },
  };
}
