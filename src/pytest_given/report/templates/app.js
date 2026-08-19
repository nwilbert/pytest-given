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
  if (s && ids.includes(s)) return s;
  // An activity filter names the story it came from. A pasted `#activity-filter=`
  // link carries no `story=` (the Scenarios view doesn't write one), so read it
  // from the filter — otherwise the Stories tab opens on an unrelated story.
  const fromFilter = (params.get('activity-filter') || '').split(':')[0];
  if (ids.includes(fromFilter)) return fromFilter;
  return ids[0] || null;
}

// --- Alpine app ---
// Buckets for scenarios with nothing on an axis. Both are selectable
// filters, so the tokens have to survive a URL: a leading '!' cannot start a
// term id (they are slugs) and is implausible as a tag.
const NO_TERMS = '!no-terms';
const NO_TAGS = '!untagged';

function reportApp() {
  const data = window.__REPORT_DATA__;
  const storyIds = window.__storyIds || [];
  const glossaryTerms = (data.glossary && data.glossary.terms) || [];
  // Scenario -> covered activity ids, and activity key -> its prose. The story
  // markup paints that prose as pills, which is unreadable as a filter label.
  const scenarioActivities = window.__scenarioActivities || {};
  const activityLabels = window.__activityLabels || {};
  const hasGlossary = glossaryTerms.length > 0;
  // Term id -> canonical display name, for the Terms browse axis.
  const termNames = {};
  for (const t of glossaryTerms) termNames[t.id] = t.canonical;
  // __termScenarios is term -> scenarios; the sidebar needs the inverse.
  const scenarioTerms = {};
  for (const [termId, ids] of Object.entries(window.__termScenarios || {})) {
    for (const sid of ids) (scenarioTerms[sid] || (scenarioTerms[sid] = [])).push(termId);
  }
  return {
    search: '',
    // Terms is the richest axis when there is a glossary to browse; reports
    // without one have no Terms segment, so they open on Tags.
    view: hasGlossary ? 'terms' : 'tags',
    mainView: 'scenarios',
    // How the browse tree orders its groups: 'name' alphabetically, 'count'
    // by how many scenarios each holds. Ephemeral like `view` above — the
    // hash carries filters, which change what you see, not the reading order.
    sortBy: 'name',
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
    tagFilters: [],
    termFilters: [],
    moduleFilter: null,
    // '<story id>:<activity id>', set by the jump from a story activity.
    // Single-select: the Stories view is the only way in and every jump
    // replaces the last, so a second one could never be selected.
    activityFilter: null,
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
      // Term/tag/module filters each show as their own removable chip, so
      // they aren't repeated here; suppress the "All Scenarios" fallback
      // while any of them is active.
      if (parts.length) return parts.join(' · ');
      const chipped = this.termFilters.length || this.tagFilters.length
        || this.moduleFilter || this.activityFilter;
      return chipped ? '' : 'All Scenarios';
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
      const isTerms = this.view === 'terms';
      for (const s of data.scenarios) {
        if (!this._matchesFilters(s)) continue;
        let keys;
        if (isTerms) {
          const ids = scenarioTerms[s.id] || [];
          keys = ids.length ? ids : [NO_TERMS];
        } else if (this.view === 'tags') {
          keys = s.tags.length ? s.tags : [NO_TAGS];
        } else {
          keys = [s.module];
        }
        for (const k of keys) {
          if (!grouped[k]) {
            grouped[k] = {
              id: k,
              name: isTerms ? this.termLabel(k) : this.tagLabel(k),
              scenarios: [],
            };
          }
          grouped[k].scenarios.push(s);
        }
      }
      // Selected groups pin to the top so what you filtered by stays in view
      // — arriving from the Glossary tab, the term you came for is the first
      // row rather than somewhere down the list. Below that pin, the sort
      // toggle decides, the same on all three axes: alphabetical for looking
      // a name up, biggest-first for seeing where the coverage sits (ties
      // still alphabetical, so equal-sized groups keep a stable reading order).
      const byCount = this.sortBy === 'count';
      return Object.values(grouped).sort((a, b) =>
        (this.isGroupActive(a) ? 0 : 1) - (this.isGroupActive(b) ? 0 : 1)
        || (byCount ? b.scenarios.length - a.scenarios.length : 0)
        || a.name.localeCompare(b.name));
    },
    _matchesFilters(s) {
      if (s.status === 'passed' && !this.showPassed) return false;
      if (s.status === 'failed' && !this.showFailed) return false;
      if (s.status === 'skipped' && !this.showSkipped) return false;
      // A scenario has exactly one module, so this axis stays single-select.
      if (this.moduleFilter && s.module !== this.moduleFilter) return false;
      // Tags and terms are set-valued, so several of them narrow with AND:
      // the scenario must carry every selected one, not any of them.
      for (const tag of this.tagFilters) {
        if (tag === NO_TAGS) {
          if (s.tags.length) return false;
        } else if (!s.tags.includes(tag)) return false;
      }
      for (const termId of this.termFilters) {
        if (termId === NO_TERMS) {
          if ((scenarioTerms[s.id] || []).length) return false;
        } else if (!(window.__termScenarios[termId] || []).includes(s.id)) {
          return false;
        }
      }
      if (this.activityFilter) {
        const [storyId, activityId] = this.activityFilter.split(':');
        if (s.story_id !== storyId) return false;
        if (!(scenarioActivities[s.id] || []).includes(Number(activityId))) {
          return false;
        }
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
    goToScenarioFresh(nodeId) {
      // Jumping in from a story activity: clear whatever was filtering the
      // Scenarios view first, or the scenario you asked for can land behind
      // a filter that hides it. Kept out of goToScenario itself, which also
      // serves `#scenario=` deep links where the hash's own filters must win.
      this.resetFilters();
      this.goToScenario(nodeId);
    },
    resetFilters() {
      this.tagFilters = [];
      this.termFilters = [];
      this.moduleFilter = null;
      this.activityFilter = null;
      this.search = '';
      this.showPassed = true;
      this.showFailed = true;
      this.showSkipped = true;
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
      // A jump from the Glossary tab is navigation, not refinement: it shows
      // the term you clicked, on its own, rather than intersecting it with
      // whatever the Scenarios view was already filtered by.
      this.resetFilters();
      this.termFilters = [id];
      this.mainView = 'scenarios';
      // Reveal the active term in the sidebar rather than landing on an
      // unrelated axis, mirroring what filterByTag does for tags.
      if (hasGlossary) this.view = 'terms';
    },
    filterScenariosByActivity(key) {
      // Navigation, not refinement — the same rule filterScenariosByTerm
      // follows: the activity arrives on its own rather than intersected with
      // whatever the Scenarios view was already filtered by.
      this.resetFilters();
      this.activityFilter = key;
      // Keep the timeline lit on the activity you left from, so the Stories
      // tab is a way back rather than a fresh start.
      this.highlightedActivities = { [key.split(':')[1]]: true };
      this.mainView = 'scenarios';
    },
    clearActivityFilter() {
      this.activityFilter = null;
    },
    activityLabel(key) {
      if (!key) return '';
      // Activities are numbered in the timeline, but the number means nothing
      // in the Scenarios view — so the chip leads with the prose and keeps the
      // number as the pointer back into the story.
      const number = key.split(':')[1];
      const text = activityLabels[key];
      return text ? `Activity ${number}: ${text}` : `Activity ${number}`;
    },
    removeTermFilter(id) {
      this.termFilters = this.termFilters.filter(t => t !== id);
    },
    removeTagFilter(tag) {
      this.tagFilters = this.tagFilters.filter(t => t !== tag);
    },
    clearModuleFilter() {
      this.moduleFilter = null;
    },
    termLabel(id) {
      if (id === NO_TERMS) return 'no terms';
      // Term ids are slugs ('file-glossary'); the report speaks canonical
      // names ('File glossary'). Falls back to the id for a term the
      // glossary no longer carries.
      return termNames[id] || id;
    },
    tagLabel(tag) {
      return tag === NO_TAGS ? 'untagged' : tag;
    },
    isGroupActive(group) {
      if (this.view === 'terms') return this.termFilters.includes(group.id);
      if (this.view === 'tags') return this.tagFilters.includes(group.id);
      return this.moduleFilter === group.id;
    },
    onGroupClick(group) {
      // In the Terms view the group name is the filter control: unlike tags,
      // a term has no pill on the scenario card to activate a filter from,
      // so the sidebar has to own that affordance. The chevron still expands
      // (its own click stops propagation before reaching here).
      if (this.view === 'terms') {
        this.termFilters = this.termFilters.includes(group.id)
          ? this.termFilters.filter(t => t !== group.id)
          : [...this.termFilters, group.id];
      } else if (this.view === 'tags') {
        this.filterByTag(group.id);
      } else {
        // Single-select: a scenario has one module, so intersecting two of
        // them could only ever be empty.
        this.moduleFilter = this.moduleFilter === group.id ? null : group.id;
      }
    },
    filterByTag(tag) {
      if (this.tagFilters.includes(tag)) {
        this.tagFilters = this.tagFilters.filter(t => t !== tag);
      } else {
        this.tagFilters = [...this.tagFilters, tag];
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
      ['tagFilters', 'termFilters', 'moduleFilter', 'activityFilter', 'showPassed', 'showFailed', 'showSkipped'].forEach(key => {
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
        // The row's jump control sits inside the row and has its own
        // destination; selecting the row as well would fight it.
        if (event.target.closest('[data-activity-jump]')) return;
        this.toggleActivityHighlight(chip.dataset.activityId);
      });
      // The selected activity row's jump control: filter the Scenarios view
      // down to the scenarios covering that activity.
      document.addEventListener('click', (event) => {
        const jump = event.target.closest('[data-activity-jump]');
        if (!jump) return;
        this.filterScenariosByActivity(jump.dataset.activityJump);
      });
      // Story-view scenario card titles jump to the scenario in the Scenarios view.
      document.addEventListener('click', (event) => {
        const link = event.target.closest('[data-goto-scenario]');
        if (!link) return;
        event.preventDefault();
        this.goToScenarioFresh(link.dataset.gotoScenario);
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
      // Comma-separated; a single-value link from an older report still reads.
      if (params.has('tag')) this.tagFilters = params.get('tag').split(',').filter(Boolean);
      else this.tagFilters = [];
      if (params.has('module')) this.moduleFilter = params.get('module');
      else this.moduleFilter = null;
      // Comma-separated; a single-term link from an older report still reads.
      if (params.has('term-filter')) {
        this.termFilters = params.get('term-filter').split(',').filter(Boolean);
      } else {
        this.termFilters = [];
      }
      if (params.has('activity-filter')) this.activityFilter = params.get('activity-filter');
      else this.activityFilter = null;
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
      if (this.tagFilters.length) params.set('tag', this.tagFilters.join(','));
      if (this.moduleFilter) params.set('module', this.moduleFilter);
      if (this.termFilters.length) params.set('term-filter', this.termFilters.join(','));
      if (this.activityFilter) params.set('activity-filter', this.activityFilter);

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
