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
    glossaryDefinitionFilter: 'all',
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
    expandedTags: {},
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
      const btn = event.currentTarget;
      // Only flip to the "copied" state once the URL is actually on the
      // clipboard — otherwise the icon would claim success even where the
      // copy silently failed (e.g. a report served over http://).
      this._copyText(window.location.href).then((ok) => {
        if (!ok) return;
        btn.classList.add('anchor-copied');
        setTimeout(() => btn.classList.remove('anchor-copied'), 1200);
      });
    },
    _copyText(text) {
      // navigator.clipboard exists only in secure contexts (https, file://);
      // a report opened over plain http:// has none, so fall back to the
      // legacy execCommand path. Also fall back if writeText rejects.
      if (navigator.clipboard && navigator.clipboard.writeText) {
        return navigator.clipboard.writeText(text).then(
          () => true,
          () => this._execCopy(text),
        );
      }
      return Promise.resolve(this._execCopy(text));
    },
    _execCopy(text) {
      try {
        const ta = document.createElement('textarea');
        ta.value = text;
        ta.style.position = 'fixed';
        ta.style.opacity = '0';
        document.body.appendChild(ta);
        ta.select();
        const ok = document.execCommand('copy');
        document.body.removeChild(ta);
        return ok;
      } catch (err) {
        return false;
      }
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
    setHoverRow(rowEl) {
      const scope = rowEl?.closest('.scenario');
      if (!scope) return;
      const values = {};
      // `data-subst` rather than `data-param`: the highlight keys on
      // `data-param`, which attachment cells and tree badges also carry, and
      // writing textContent into a badge would destroy its inline SVG.
      rowEl.querySelectorAll('td[data-subst]').forEach(td => {
        values[td.dataset.subst] = td.textContent.trim();
      });
      scope.querySelectorAll('span[data-subst]').forEach(span => {
        const val = values[span.dataset.subst];
        if (val === undefined) return;
        // Stash the original {token} once so re-entry stays idempotent.
        if (span.dataset.token === undefined) span.dataset.token = span.textContent;
        span.textContent = val;
        span.classList.add('param-substituted');
      });
    },
    clearHoverRow(rowEl) {
      const scope = rowEl?.closest('.scenario');
      if (!scope) return;
      scope.querySelectorAll('span.param-substituted').forEach(span => {
        if (span.dataset.token !== undefined) {
          span.textContent = span.dataset.token;
          delete span.dataset.token;
        }
        span.classList.remove('param-substituted');
      });
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
      // Story-view scenario card titles jump to the scenario in the Scenarios view.
      document.addEventListener('click', (event) => {
        const link = event.target.closest('[data-goto-scenario]');
        if (!link) return;
        event.preventDefault();
        this.goToScenario(link.dataset.gotoScenario);
      });
      this._initTermTooltip();
    },
    // Single shared tooltip for every term-ref pill. We position it with
    // `fixed` from the pill's bounding box (rather than a CSS-only tooltip)
    // because pills live inside `overflow: hidden` collapsible bodies that
    // would otherwise clip an absolutely positioned child.
    _initTermTooltip() {
      const tip = document.getElementById('term-tip');
      if (!tip) return;
      const nameEl = tip.querySelector('.term-tip-name');
      const defEl = tip.querySelector('.term-tip-def');
      const hide = () => { tip.hidden = true; };
      document.addEventListener('pointerover', (event) => {
        const pill = event.target.closest('[data-term-name]');
        if (!pill) { return; }
        nameEl.textContent = pill.dataset.termName;
        const def = pill.dataset.termDef || '';
        // innerHTML because a definition carries inline markup. Safe not
        // because the source is trusted — a term definition is ordinary
        // report data — but because render_inline_markdown escapes the text
        // first and only re-admits <br>/<code>/<strong>/<em>, none of which
        // take attributes. Keep that invariant if you extend the renderer.
        defEl.innerHTML = def;
        defEl.hidden = !def;
        tip.hidden = false;
        const pillRect = pill.getBoundingClientRect();
        const tipRect = tip.getBoundingClientRect();
        const margin = 6;
        let top = pillRect.top - tipRect.height - margin;
        if (top < margin) top = pillRect.bottom + margin;  // flip below if clipped
        let left = pillRect.left;
        const maxLeft = window.innerWidth - tipRect.width - margin;
        if (left > maxLeft) left = maxLeft;
        if (left < margin) left = margin;
        tip.style.top = top + 'px';
        tip.style.left = left + 'px';
      });
      document.addEventListener('pointerout', (event) => {
        const pill = event.target.closest('[data-term-name]');
        if (!pill) return;
        if (event.relatedTarget && pill.contains(event.relatedTarget)) return;
        hide();
      });
      // Tooltip is positioned in viewport coords; any scroll invalidates it.
      window.addEventListener('scroll', hide, true);
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
