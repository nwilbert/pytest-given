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

// Mirrors `tab_visibility`: these are the reports that render each tab.
function hasStories() {
  return (window.__REPORT_DATA__.story_ids || []).length > 0;
}

function hasTerms() {
  return (window.__REPORT_DATA__.term_ids || []).length > 0;
}

function deserializeView(params) {
  // Gated on the tab existing: a stale `#view=glossary` would otherwise hide
  // the Scenarios view behind an empty one, with no tab bar left to leave by.
  const v = params.get('view');
  if (v === 'stories' && hasStories()) return 'stories';
  if (v === 'glossary' && hasTerms()) return 'glossary';
  return 'scenarios';
}

function deserializeStory(params) {
  const s = params.get('story');
  const ids = window.__REPORT_DATA__.story_ids || [];
  if (s && ids.includes(s)) return s;
  // A sentence filter names the story it came from. A pasted `#sentence-filter=`
  // link carries no `story=` (the Scenarios view doesn't write one), so read it
  // from the filter — otherwise the Stories tab opens on an unrelated story.
  const fromFilter = (params.get('sentence-filter') || '').split(':')[0];
  if (ids.includes(fromFilter)) return fromFilter;
  return ids[0] || null;
}

// Own keys only: these are read from the URL fragment, and a bare `map[key]`
// answers `#term-filter=toString` with a function off Object.prototype.
function lookup(map, key, fallback) {
  return Object.hasOwn(map, key) ? map[key] : fallback;
}

// --- Alpine app ---
// Buckets for scenarios with nothing on an axis. Both are selectable filters,
// so the tokens have to survive a URL: a leading '!' cannot start a term id
// (they are slugs) and is implausible as a tag.
const NO_TERMS = '!no-terms';
const NO_TAGS = '!untagged';

// Sidebar width bounds, in CSS px. The floor is where a module row still fits
// a segment plus its count; the ceiling keeps the scenario column the wider of
// the two. `aria-valuemin` / `aria-valuemax` on the handle repeat these.
const SIDEBAR_MIN = 180;
const SIDEBAR_MAX = 480;
const SIDEBAR_DEFAULT = 260;
const clampSidebar = w => Math.min(SIDEBAR_MAX, Math.max(SIDEBAR_MIN, Math.round(w)));

// --- Theme ---
// The head script in report.html.j2 painted the page before Alpine loaded and
// owns the mechanism; this side only mirrors its `choice` for the toggle and
// calls its `set`.
const theme = window.__REPORT_THEME__;

// Two browse axes are trees: modules split on '.', tags on '/'. A filter on
// either selects its own key and everything below it — a package takes its
// modules, `ticket` takes `ticket/ABC-123`.
const MODULE_SEP = '.';
const TAG_SEP = '/';
function underPrefix(key, filter, sep) {
  return key === filter || key.startsWith(filter + sep);
}

// Every prefix of a key, the key itself included: `a.b.c` -> a, a.b, a.b.c.
function prefixesOf(key, sep) {
  const parts = key.split(sep);
  return parts.map((_, i) => parts.slice(0, i + 1).join(sep));
}

// Segments every module shares carry no information — `tests` above a suite
// rooted there is a row and an indent that say nothing. Never eats a module's
// last segment, or a lone module would render nameless. Tags get no such
// stripping: a shared tag prefix is a heading the author wrote on purpose.
function commonDepth(modules) {
  if (!modules.length) return 0;
  const split = modules.map(m => m.split(MODULE_SEP));
  const first = split[0];
  let i = 0;
  while (i < first.length - 1
         && split.every(parts => parts.length > i + 1 && parts[i] === first[i])) i++;
  return i;
}

function reportApp() {
  // The slim projection `html_renderer._app_data` emits, not the whole report.
  const data = window.__REPORT_DATA__;
  const storyIds = data.story_ids || [];
  const glossaryTerms = (data.glossary && data.glossary.terms) || [];
  // Scenario -> story -> covered sentence ids, and sentence key -> its label.
  // The story markup paints the prose as pills, unreadable as a filter label.
  const scenarioSentences = data.scenario_sentences || {};
  const sentenceLabels = data.sentence_labels || {};
  const hasGlossary = glossaryTerms.length > 0;
  const allModules = [...new Set(data.scenarios.map(s => s.module))];
  // Term id -> canonical display name, for the Terms browse axis.
  const termNames = {};
  for (const t of glossaryTerms) termNames[t.id] = t.canonical;
  // Term id -> the term itself, for the hover tooltip. Looked up by id rather
  // than carried on every ref: a term used N times would otherwise repeat its
  // whole definition N times in the markup.
  const termsById = new Map(glossaryTerms.map((t) => [t.id, t]));
  const termScenarios = data.term_scenarios || {};
  // termScenarios is term -> scenarios; the sidebar needs the inverse.
  const scenarioTerms = {};
  for (const [termId, ids] of Object.entries(termScenarios)) {
    for (const sid of ids) (scenarioTerms[sid] || (scenarioTerms[sid] = [])).push(termId);
  }
  // Filtering is the hot path: six Alpine effects rescan every scenario per
  // filter change, so anything derivable once is derived here.
  const searchHaystacks = data.scenarios.map(
    s => (s.narration.text + ' ' + s.tags.join(' ')).toLowerCase(),
  );
  // Every status in filter order, labelled as the Markdown report words them.
  const STATUS_LABELS = data.status_labels;
  const STATUSES = Object.keys(STATUS_LABELS);
  const allStatusesShown = () => Object.fromEntries(STATUSES.map(s => [s, true]));
  const statusCounts = Object.fromEntries(STATUSES.map(s => [s, 0]));
  for (const s of data.scenarios) statusCounts[s.status] += 1;
  const statusesPresent = STATUSES.filter(s => statusCounts[s] > 0);
  const moduleSkipDepth = commonDepth(allModules);
  function termLabel(id) {
    if (id === NO_TERMS) return 'no terms';
    // Term ids are slugs ('file-glossary'); the report speaks canonical
    // names ('File glossary'). Falls back to the id for an unknown term.
    return lookup(termNames, id, id);
  }
  function tagLabel(tag) {
    return tag === NO_TAGS ? 'untagged' : tag;
  }
  // The browse axes. A node counts scenarios, not keys — a scenario tagged
  // `ticket/A` and `ticket/B` is one row under `ticket` — so `reach` lists
  // once per scenario every key it counts under: each of its own keys and
  // every prefix of them. Term ids are slugs and never split, so the same
  // tree renders them flat. Whether an axis nests at all is read off the
  // whole report, not the filtered rows: the chevron gutter would otherwise
  // shift every label as a filter hides the last branch.
  const reachOf = (keys, sep) => [...new Set(keys.flatMap(key => prefixesOf(key, sep)))];
  const axes = {
    modules: {
      sep: MODULE_SEP, skip: moduleSkipDepth, label: name => name,
      reach: data.scenarios.map(s => prefixesOf(s.module, MODULE_SEP)),
      nests: allModules.some(m => m.split(MODULE_SEP).length > moduleSkipDepth + 1),
    },
    tags: {
      sep: TAG_SEP, skip: 0, label: tagLabel,
      reach: data.scenarios.map(s => reachOf(s.tags.length ? s.tags : [NO_TAGS], TAG_SEP)),
      nests: data.scenarios.some(s => s.tags.some(tag => tag.includes(TAG_SEP))),
    },
    terms: {
      sep: TAG_SEP, skip: 0, label: termLabel,
      reach: data.scenarios.map(s => lookup(scenarioTerms, s.id, [NO_TERMS])),
      nests: false,
    },
  };
  // Closure variables, not state: writing one from inside a reactive effect
  // that also reads it would re-trigger that effect.
  let visibleCache = null;
  let termCountCache = null;
  return {
    search: '',
    // Modules is the only axis every report has: a suite may carry no tags and
    // no glossary, but every scenario has a module. So it leads the segments
    // and opens by default, and no report can open on an empty browse tree.
    view: 'modules',
    mainView: 'scenarios',
    // How the browse tree orders its groups. Ephemeral like `view` above —
    // the hash carries filters, which change what you see, not the order.
    sortBy: 'name',
    // Applied as `--sidebar-w` on <body>, so one drag resizes all three views'
    // sidebars. Deliberately not in the hash with the filters: a width is a
    // property of the window it is read in, not of the view a link points at,
    // and it would otherwise travel to whoever the link is shared with.
    sidebarWidth: SIDEBAR_DEFAULT,
    // What the toggle highlights, so the control agrees with the paint.
    themeChoice: theme.choice,
    selectedStory: storyIds[0] || null,
    glossarySearch: '',
    glossaryKindFilter: { actor: true, object: true, activity: true, kindless: true },
    glossaryDefinitionFilter: 'all',
    expandedTerms: {},
    shownStatuses: allStatusesShown(),
    expandedGroups: {},
    expandedSteps: {},
    expandedAttachments: {},
    expandedScenarios: {},
    expandedTags: {},
    tagFilters: [],
    termFilters: [],
    moduleFilter: null,
    // '<story id>:<sentence id>', set by the jump from a story sentence.
    // Single-select: every jump replaces the last, so a second one could
    // never be selected.
    sentenceFilter: null,
    _suppressHashWrite: false,
    highlightedSentences: {},
    // Presence sets: `delete` rather than `= false` keeps the matching
    // "is anything open?" getters a plain key count.
    _toggle(map, key) {
      if (map[key]) delete map[key];
      else map[key] = true;
    },
    get anySentencesHighlighted() {
      return Object.keys(this.highlightedSentences).length > 0;
    },
    toggleSentenceHighlight(id) {
      this._toggle(this.highlightedSentences, id);
    },
    clearSentenceHighlights() {
      this.highlightedSentences = {};
    },
    // Sentence ids are per-story ints, so a highlight cannot travel. Cleared
    // here rather than in a `selectedStory` watcher, which would fire after
    // `_readHash` had set story and highlights together and undo the second.
    selectStory(id) {
      if (this.selectedStory === id) return;
      this.selectedStory = id;
      this.highlightedSentences = {};
    },
    // A Stories-view slot borrows its card from the Scenarios view rather than
    // the page rendering each scenario again per story; Alpine initializes the
    // fresh clones on insertion, under the story's own open-state maps.
    fillStoryCards() {
      if (this.mainView !== 'stories' || !this.selectedStory) return;
      const story = document.querySelector(
        `#view-stories .view-main > [data-story-id="${CSS.escape(this.selectedStory)}"]`,
      );
      if (!story) return;
      // Two stories can list one scenario, so the id prefix names the story.
      const prefix = `story-${this.selectedStory}-`;
      for (const slot of story.querySelectorAll('[data-clone-of]:not([data-filled])')) {
        const card = document.getElementById('scenario-' + slot.dataset.cloneOf);
        const header = card.querySelector(':scope > .scenario-header').cloneNode(true);
        const body = card.querySelector(':scope > .scenario-body').cloneNode(true);
        for (const part of [header, body]) this._prepareClone(part, prefix);
        slot.prepend(header);
        slot.append(body);
        slot.dataset.filled = '';
      }
    },
    // A clone copies the original's DOM as it stands, including what the hover
    // handlers wrote into it imperatively, which nothing would undo on the copy.
    _prepareClone(part, prefix) {
      for (const el of [part, ...part.querySelectorAll('[id], [aria-controls]')]) {
        if (el.id) el.id = prefix + el.id;
        const controls = el.getAttribute('aria-controls');
        if (controls) el.setAttribute('aria-controls', prefix + controls);
      }
      this._clearParamHighlight(part);
      this._restoreTokens(part);
      this._clearPhaseOutline(part);
      // Likewise the tick a copy just set, which the copy's timer clears only
      // on the original.
      part.querySelectorAll('.anchor-copied').forEach(el => el.classList.remove('anchor-copied'));
      // A tag here shows the active filter but toggles nothing, so it is not
      // announced as a pressed toggle. Dropped before Alpine sees the clone.
      part.querySelectorAll('.scenario-tag').forEach(el => {
        el.removeAttribute(':aria-pressed');
        el.removeAttribute('aria-pressed');
      });
    },
    // Story-view scenario cards filter on the selected sentences: a card stays
    // visible when nothing is selected, or when it covers ANY selected sentence.
    sentenceSelectionMatches(coveredIds) {
      if (!this.anySentencesHighlighted) return true;
      return coveredIds.some(id => this.highlightedSentences[id]);
    },
    // Terms of one kind surviving the search and definition filters. The
    // headings and their counts are Jinja-rendered report totals, so without
    // this a search matching nothing leaves them standing over an empty page.
    visibleTermCount(kind) {
      return this._termCounts()[kind] || 0;
    },
    // One pass per filter change, not the twelve the four kind sections ask
    // for. Cached as `_visible` is, and for the same reason.
    _termCounts() {
      const key = this.glossarySearch + '\u0000' + this.glossaryDefinitionFilter;
      if (termCountCache && termCountCache.key === key) return termCountCache.value;
      const q = this.glossarySearch.toLowerCase();
      const wantUndefined = this.glossaryDefinitionFilter === 'undefined';
      const counts = {};
      for (const t of glossaryTerms) {
        if (this.glossaryDefinitionFilter !== 'all'
            && wantUndefined !== (t.definition === null || t.definition === undefined)) continue;
        if (q && !t.canonical.toLowerCase().includes(q)) continue;
        const kind = t.kind || 'kindless';
        counts[kind] = (counts[kind] || 0) + 1;
      }
      termCountCache = { key, value: counts };
      return counts;
    },
    visibleTermLabel(kind) {
      const n = this.visibleTermCount(kind);
      return n + (n === 1 ? ' term' : ' terms');
    },
    get anyTermsVisible() {
      const counts = this._termCounts();
      return ['actor', 'object', 'activity', 'kindless']
        .some(k => this.glossaryKindFilter[k] && counts[k] > 0);
    },
    get anyTermsExpanded() {
      return Object.keys(this.expandedTerms).length > 0;
    },
    toggleAllTerms() {
      const expand = !this.anyTermsExpanded;
      const ids = window.__REPORT_DATA__.term_ids || [];
      if (expand) {
        ids.forEach(id => { this.expandedTerms[id] = true; });
      } else {
        this.expandedTerms = {};
      }
    },
    get filterSummary() {
      const parts = [];
      const shown = statusesPresent.filter(s => this.shownStatuses[s]);
      if (shown.length !== statusesPresent.length) {
        parts.push(shown.length ? shown.map(s => STATUS_LABELS[s]).join(', ') : 'no statuses');
      }
      if (this.search) parts.push('"' + this.search + '"');
      // Term/tag/module filters each have their own removable chip, so they
      // are not repeated here — but they do suppress "All Scenarios".
      // An em space: this lands in one x-text, so the gap has to be a character.
      if (parts.length) return parts.join('\u2003');
      const chipped = this.termFilters.length || this.tagFilters.length
        || this.moduleFilter || this.sentenceFilter;
      return chipped ? '' : 'All Scenarios';
    },
    get formattedTimestamp() {
      const d = new Date(data.metadata.timestamp);
      if (isNaN(d)) return data.metadata.timestamp;
      return d.toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' })
        + ' at ' + d.toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit', hour12: false });
    },
    get counts() {
      return statusCounts;
    },
    get filteredCount() {
      return this._visible().size;
    },
    // Computed once per filter change instead of once per reader. Reading the
    // filter state here still registers each caller's reactive dependencies;
    // the cache only stops the O(n) scan repeating within one pass. The array
    // filters compare by identity — both are replaced, never mutated.
    _visible() {
      const state = [
        ...STATUSES.map(s => this.shownStatuses[s]),
        this.moduleFilter, this.sentenceFilter, this.search,
        this.tagFilters, this.termFilters,
      ];
      if (visibleCache && visibleCache.state.every((v, i) => v === state[i])) {
        return visibleCache.value;
      }
      const query = this.search.toLowerCase();
      const value = new Set();
      for (let i = 0; i < data.scenarios.length; i++) {
        if (this._matchesFilters(data.scenarios[i], i, query)) value.add(i);
      }
      visibleCache = { state, value };
      return value;
    },
    // Every axis renders as the same flat list of rows carrying their own
    // `depth`, so one template serves all three; only interior rows have
    // children to expand. Whether the axis nests at all decides the chevron
    // gutter: a flat list keeps none, one hierarchical key gives every row
    // the spacer so leaves align.
    get groups() {
      return this._treeRows(axes[this.view], this._activeFilters());
    },
    get groupsNest() {
      return axes[this.view].nests;
    },
    // The selected keys on the current axis, as a list even for the
    // single-select module axis, so the tree and its active check read one
    // shape.
    _activeFilters() {
      if (this.view === 'terms') return this.termFilters;
      if (this.view === 'tags') return this.tagFilters;
      return this.moduleFilter ? [this.moduleFilter] : [];
    },
    // A path tree, flattened depth-first into rows. A row is visible only
    // while every ancestor is expanded, so collapsing a node hides the
    // subtree without rebuilding it. `skip` drops leading segments from every
    // row (module depth comes from every module in the report, not the
    // filtered subset: selecting a package narrows the tree to it, and a
    // prefix recomputed from that subset would strip the selected row itself
    // out of view); `filters` are the active prefix filters.
    _treeRows({ sep, skip, reach, label }, filters) {
      const counts = {};
      for (const i of this._visible()) {
        for (const id of reach[i]) counts[id] = (counts[id] || 0) + 1;
      }
      const root = {};
      for (const id of Object.keys(counts)) {
        let node = root;
        const prefixes = prefixesOf(id, sep);
        for (let i = skip; i < prefixes.length; i++) {
          const key = prefixes[i];
          const name = key.slice(key.lastIndexOf(sep) + 1);
          node = (node[key] || (node[key] = { __id: key, __name: name, __kids: {} })).__kids;
        }
      }
      const rows = [];
      const walk = (kids, depth, visible) => {
        const level = Object.values(kids).map(node => ({
          node, id: node.__id, name: label(node.__name), depth,
          hasChildren: Object.keys(node.__kids).length > 0, count: counts[node.__id],
        }));
        for (const row of this._ordered(level, filters)) {
          if (visible) rows.push(row);
          // A node on the path to a selected one opens whether or not it was
          // expanded by hand, so the selected row is never stranded inside a
          // collapsed ancestor — on a `#module=` or `#tag=` deep link there
          // was no chance to expand it, and after a click it must stay
          // visible to be clicked again.
          const onPath = filters.some(filter => filter.startsWith(row.id + sep));
          walk(row.node.__kids, depth + 1,
               visible && (!!this.expandedGroups[row.id] || onPath));
        }
      };
      walk(root, 0, true);
      return rows.map(({ node, ...row }) => row);
    },
    // Selected groups pin to the top so what you filtered by stays in view:
    // arriving from the Glossary tab, the term you came for is the first row
    // rather than somewhere down the list. Below the pin the sort toggle
    // decides, with ties alphabetical so the order stays stable.
    _ordered(rows, filters) {
      const byCount = this.sortBy === 'count';
      return rows.sort((a, b) =>
        (filters.includes(a.id) ? 0 : 1) - (filters.includes(b.id) ? 0 : 1)
        || (byCount ? b.count - a.count : 0)
        || a.name.localeCompare(b.name));
    },
    // Called from `_visible` alone. `index` addresses the precomputed
    // haystack; `query` is the search box, lowercased once by the caller.
    _matchesFilters(s, index, query) {
      if (!this.shownStatuses[s.status]) return false;
      // A scenario has exactly one module, so this axis is single-select. The
      // filter is a path prefix, not an exact id: selecting a package in the
      // browse tree takes everything under it.
      if (this.moduleFilter && !underPrefix(s.module, this.moduleFilter, MODULE_SEP)) {
        return false;
      }
      // Tags and terms are set-valued, so several of them narrow with AND:
      // the scenario must carry every selected one, not any of them. A tag
      // filter is a prefix like the module filter, met by any tag under it.
      for (const tag of this.tagFilters) {
        if (tag === NO_TAGS) {
          if (s.tags.length) return false;
        } else if (!s.tags.some(own => underPrefix(own, tag, TAG_SEP))) return false;
      }
      // Read off the scenario's own term list, not the term's scenario list:
      // one index either way, but a term names thousands of scenarios and a
      // scenario a handful, and the long side made the pass quadratic.
      if (this.termFilters.length) {
        const own = lookup(scenarioTerms, s.id, []);
        for (const termId of this.termFilters) {
          if (termId === NO_TERMS) {
            if (own.length) return false;
          } else if (!own.includes(termId)) {
            return false;
          }
        }
      }
      if (this.sentenceFilter) {
        const [storyId, sentenceId] = this.sentenceFilter.split(':');
        const covered = (scenarioSentences[s.id] || {})[storyId] || [];
        if (!covered.includes(Number(sentenceId))) return false;
      }
      if (query && !searchHaystacks[index].includes(query)) return false;
      return true;
    },
    toggleGroup(name) {
      this._toggle(this.expandedGroups, name);
    },
    // Pointer capture on the handle keeps the drag alive over the iframe-free
    // but text-heavy main column, and delivers the release even if the pointer
    // leaves the window. The listeners live on the handle for the same reason.
    startSidebarResize(event) {
      // Primary button only: a right-click drags the sidebar *and* opens the
      // context menu, whose swallowed release can leave the drag live.
      if (event.button !== 0) return;
      // preventDefault stops the drag from placing a caret or starting a text
      // selection — but it also suppresses the focus a click would otherwise
      // give a tabindex'd element, which left the arrow keys dead for anyone
      // who grabbed the seam and then reached for the keyboard. So focus it
      // here, rather than depending on a default we just declined.
      event.preventDefault();
      const handle = event.currentTarget;
      handle.focus();
      const startX = event.clientX;
      const startWidth = this.sidebarWidth;
      handle.setPointerCapture(event.pointerId);
      document.body.classList.add('resizing-sidebar');
      const drag = e => { this.sidebarWidth = clampSidebar(startWidth + e.clientX - startX); };
      const stop = () => {
        handle.removeEventListener('pointermove', drag);
        handle.removeEventListener('pointerup', stop);
        handle.removeEventListener('pointercancel', stop);
        document.body.classList.remove('resizing-sidebar');
      };
      handle.addEventListener('pointermove', drag);
      handle.addEventListener('pointerup', stop);
      handle.addEventListener('pointercancel', stop);
    },
    nudgeSidebar(step) {
      this.sidebarWidth = clampSidebar(this.sidebarWidth + step);
    },
    resetSidebar() {
      this.sidebarWidth = SIDEBAR_DEFAULT;
    },
    setTheme(choice) {
      this.themeChoice = choice;
      theme.set(choice);
    },
    toggleStep(stepId) {
      this._toggle(this.expandedSteps, stepId);
    },
    toggleScenario(index) {
      this._toggle(this.expandedScenarios, index);
    },
    toggleTerm(id) {
      this._toggle(this.expandedTerms, id);
    },
    get anyScenariosExpanded() {
      for (const i of this._visible()) if (this.expandedScenarios[i]) return true;
      return false;
    },
    toggleAllScenarios() {
      const expand = !this.anyScenariosExpanded;
      for (const i of this._visible()) {
        if (expand) this.expandedScenarios[i] = true;
        else delete this.expandedScenarios[i];
      }
    },
    isVisible(index) {
      return this._visible().has(index);
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
      // Jumping in from a story sentence: clear whatever was filtering the
      // Scenarios view first, or the scenario you asked for can land behind a
      // filter that hides it. Kept out of goToScenario, which also serves
      // `#scenario=` deep links where the hash's own filters must win.
      this.resetFilters();
      this.goToScenario(nodeId);
    },
    resetFilters() {
      this.tagFilters = [];
      this.termFilters = [];
      this.moduleFilter = null;
      this.sentenceFilter = null;
      this.search = '';
      this.shownStatuses = allStatusesShown();
    },
    goToTerm(id) {
      // A stale `#term=` link would otherwise open an empty Glossary tab.
      if (!Object.hasOwn(termNames, id)) return;
      this.mainView = 'glossary';
      this.expandedTerms[id] = true;
      this.$nextTick(() => {
        const el = document.getElementById('term-' + id);
        if (el) el.scrollIntoView({ behavior: 'smooth', block: 'start' });
      });
    },
    filterScenariosByTerm(id) {
      // Navigation, not refinement: the term arrives on its own rather than
      // intersected with whatever the Scenarios view was already filtered by.
      this.resetFilters();
      this.termFilters = [id];
      this.mainView = 'scenarios';
      // Reveal the active term rather than landing on an unrelated axis.
      if (hasGlossary) this.view = 'terms';
    },
    filterScenariosBySentence(key) {
      // Navigation, not refinement, as for a term.
      this.resetFilters();
      this.sentenceFilter = key;
      // Keep the timeline lit on the sentence you left from, so the Stories
      // tab is a way back rather than a fresh start.
      this.highlightedSentences = { [key.split(':')[1]]: true };
      this.mainView = 'scenarios';
    },
    clearSentenceFilter() {
      this.sentenceFilter = null;
    },
    sentenceLabel(key) {
      if (!key) return '';
      // A key from a stale link names no sentence here; its number still points.
      return lookup(sentenceLabels, key, `Sentence ${key.split(':')[1]}`);
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
    termLabel,
    tagLabel,
    isGroupActive(group) {
      return this._activeFilters().includes(group.id);
    },
    onGroupClick(group) {
      const selecting = !this.isGroupActive(group);
      // In the Terms view the group name is the filter control: unlike a tag,
      // a term has no pill on the scenario card to filter from, so the sidebar
      // owns that affordance. The chevron still expands (its own click stops
      // propagation before reaching here).
      if (this.view === 'terms') {
        this.termFilters = selecting
          ? [...this.termFilters, group.id]
          : this.termFilters.filter(t => t !== group.id);
      } else if (this.view === 'tags') {
        this.filterByTag(group.id);
      } else {
        this.moduleFilter = selecting ? group.id : null;
      }
      // Selecting a package or tag prefix opens it as well: the click that
      // narrows to one is nearly always the one that wants to see what is in
      // it, and hitting the chevron is the fussier target. Deselecting leaves
      // the tree open — collapsing under the cursor loses the reader's place.
      if (selecting && group.hasChildren) this.expandedGroups[group.id] = true;
    },
    filterByTag(tag) {
      // From Stories, a tag opens the Scenarios view filtered to it alone.
      if (this.mainView === 'stories') {
        this.resetFilters();
        this.mainView = 'scenarios';
      }
      if (this.tagFilters.includes(tag)) {
        this.tagFilters = this.tagFilters.filter(t => t !== tag);
      } else {
        // One active node per path, as in the module tree: `ticket` AND
        // `ticket/CS-42` is just `ticket/CS-42`, so selecting an ancestor
        // widens to it and selecting a descendant narrows to it.
        const related = other => underPrefix(other, tag, TAG_SEP) || underPrefix(tag, other, TAG_SEP);
        this.tagFilters = [...this.tagFilters.filter(other => !related(other)), tag];
        this.view = 'tags';
      }
    },
    toggleAttachment(key) {
      if (this.expandedAttachments[key]) delete this.expandedAttachments[key];
      else this.expandedAttachments[key] = true;
    },
    // Copies the link without visiting it: writing it into the address bar
    // would overwrite the history entry holding the current filters.
    copyAnchor(hashString, event) {
      const url = window.location.href.split('#')[0] + '#' + hashString;
      const btn = event.currentTarget;
      // Only flip to the "copied" state once the URL is actually on the
      // clipboard, or the icon would claim a success that never happened.
      this._copyText(url).then((ok) => {
        if (!ok) return;
        btn.classList.add('anchor-copied');
        setTimeout(() => btn.classList.remove('anchor-copied'), 1200);
      });
    },
    _copyText(text) {
      // navigator.clipboard exists only in secure contexts (https, file://),
      // so a report served over plain http:// falls back to execCommand — as
      // does a writeText that rejects.
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
    // Scoped to one card; the `document` fallback this replaces queried the
    // whole report.
    setHoverParam(name, el) {
      const scope = el?.closest('.scenario');
      if (!scope) return;
      this._clearParamHighlight(scope);
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
      this._restoreTokens(scope);
    },
    // The undo of each hover effect, by scope rather than by the hovered
    // element: a clone being prepared is not in the page yet.
    _clearParamHighlight(scope) {
      scope.querySelectorAll('.param-highlight').forEach(e => e.classList.remove('param-highlight'));
    },
    _restoreTokens(scope) {
      scope.querySelectorAll('span.param-substituted').forEach(span => {
        if (span.dataset.token !== undefined) {
          span.textContent = span.dataset.token;
          delete span.dataset.token;
        }
        span.classList.remove('param-substituted');
      });
    },
    _clearPhaseOutline(scope) {
      scope.querySelectorAll('.phase-hover').forEach(e => e.classList.remove('phase-hover'));
      scope.querySelectorAll('.phase-outline').forEach(e => e.remove());
    },
    init() {
      this._readHash();
      // Search typing replaces the current entry (no per-keystroke history
      // spam); discrete navigations and filters push a back-able one. All
      // writes are suppressed while state is being applied FROM the hash.
      this.$watch('search', () => { if (!this._suppressHashWrite) this._writeHash('replace'); });
      ['tagFilters', 'termFilters', 'moduleFilter', 'sentenceFilter', 'shownStatuses'].forEach(key => {
        this.$watch(key, () => { if (!this._suppressHashWrite) this._writeHash('push'); });
      });
      ['mainView', 'selectedStory'].forEach(key => {
        this.$watch(key, () => {
          if (!this._suppressHashWrite) this._writeHash('push');
          this.fillStoryCards();
        });
      });
      // Once Alpine has walked the page, so the cards cloned are initialized
      // ones and a `#view=stories` link lands with its story filled.
      this.$nextTick(() => this.fillStoryCards());
      // hashchange: manual URL edits / pasted links. popstate: back/forward.
      window.addEventListener('hashchange', () => this._readHash());
      window.addEventListener('popstate', () => this._readHash());
      // Capture phase + stopPropagation so a term pill inside a clickable
      // container navigates without also triggering that container's click.
      document.addEventListener('click', (event) => {
        const pill = event.target.closest('[data-term-id]');
        if (!pill) return;
        if (pill.closest('.entry')) return;  // don't self-jump inside a glossary entry
        event.stopPropagation();
        this.goToTerm(pill.dataset.termId);
      }, true);
      document.addEventListener('click', (event) => {
        const chip = event.target.closest('[data-sentence-id]');
        if (!chip) return;
        // The row's own jump control has a different destination; selecting
        // the row as well would fight it.
        if (event.target.closest('[data-sentence-jump]')) return;
        this.toggleSentenceHighlight(chip.dataset.sentenceId);
      });
      // The jump control filters the Scenarios view down to that sentence.
      document.addEventListener('click', (event) => {
        const jump = event.target.closest('[data-sentence-jump]');
        if (!jump) return;
        this.filterScenariosBySentence(jump.dataset.sentenceJump);
      });
      // A Stories-view card's jump opens the scenario in the Scenarios view.
      document.addEventListener('click', (event) => {
        const link = event.target.closest('[data-goto-scenario]');
        if (!link) return;
        event.preventDefault();
        this.goToScenarioFresh(link.dataset.gotoScenario);
      });
      this._initTermTooltip();
      this._initParamHover();
      this._initPhaseHover();
    },
    // Parameter-table hover, delegated. A per-cell `@mouseenter` pair was
    // ~60% of every Alpine directive on a large report, and seconds of its
    // startup. `pointerover`, not `mouseenter`, because only it bubbles.
    _initParamHover() {
      let cell = null;
      let row = null;
      const leaveCell = () => { if (cell) { this.setHoverParam(null, cell); cell = null; } };
      const leaveRow = () => { if (row) { this.clearHoverRow(row); row = null; } };
      document.addEventListener('pointerover', (event) => {
        const nextRow = event.target.closest('tr[data-case-row]');
        if (nextRow !== row) {
          leaveRow();
          row = nextRow;
          if (row) this.setHoverRow(row);
        }
        const nextCell = event.target.closest('[data-param]');
        if (nextCell !== cell) {
          leaveCell();
          cell = nextCell;
          if (cell) this.setHoverParam(cell.dataset.param, cell);
        }
      });
      // A pointer leaving the window fires no further `pointerover`.
      document.addEventListener('pointerout', (event) => {
        if (event.relatedTarget) return;
        leaveRow();
        leaveCell();
      });
    },
    // Phase hover, delegated the same way: a phase block in the narration and
    // the table columns it narrates carry one `data-block`, and pointing at
    // either outlines both. The status column is a block of its own. The
    // boxes are measured, so they are redrawn whenever the table resizes
    // under a still pointer — a payload opened from its own badge, mid-hover.
    _initPhaseHover() {
      let hovered = null;
      const redraw = new ResizeObserver(() => {
        if (!hovered) return;
        this._clearPhaseOutline(hovered.scope);
        this._outlinePhase(hovered.scope, hovered.block);
      });
      const leave = () => {
        if (!hovered) return;
        redraw.disconnect();
        this._clearPhaseOutline(hovered.scope);
        hovered = null;
      };
      document.addEventListener('pointerover', (event) => {
        const el = event.target.closest('[data-block]');
        const scope = el?.closest('.scenario');
        if (hovered && scope === hovered.scope && el.dataset.block === hovered.block) return;
        leave();
        if (!scope) return;
        hovered = { scope, block: el.dataset.block };
        this._outlinePhase(scope, el.dataset.block);
        const table = scope.querySelector('.param-table');
        if (table) redraw.observe(table);
      });
      document.addEventListener('pointerout', (event) => {
        if (!event.relatedTarget) leave();
      });
    },
    // One box per run of rows: a visible row without the block's cells (an
    // error, an open payload) ends a box rather than being drawn through. A
    // collapsed payload row has no height and does not.
    _outlinePhase(scope, block) {
      const safe = CSS.escape(block);
      scope.querySelectorAll(`.phase-block[data-block="${safe}"]`).forEach(e => e.classList.add('phase-hover'));
      const table = scope.querySelector('.param-table');
      if (!table) return;
      const wrap = table.parentElement;
      const origin = wrap.getBoundingClientRect();
      const boxes = [];
      let box = null;
      for (const row of table.rows) {
        const cells = row.querySelectorAll(`[data-block="${safe}"]`);
        if (!cells.length) {
          if (row.getBoundingClientRect().height > 1) box = null;
          continue;
        }
        const first = cells[0].getBoundingClientRect();
        const last = cells[cells.length - 1].getBoundingClientRect();
        if (!box) {
          box = { left: first.left, right: last.right, top: first.top };
          boxes.push(box);
        }
        box.bottom = first.bottom;
      }
      for (const { left, right, top, bottom } of boxes) {
        const outline = document.createElement('div');
        outline.className = 'phase-outline';
        outline.style.left = `${left - origin.left + wrap.scrollLeft}px`;
        outline.style.top = `${top - origin.top}px`;
        outline.style.width = `${right - left}px`;
        outline.style.height = `${bottom - top}px`;
        wrap.appendChild(outline);
      }
    },
    // One shared tooltip for every term ref, positioned `fixed` from the
    // ref's bounding box rather than done in CSS: term refs live inside
    // `overflow: hidden` collapsible bodies, which would clip an absolutely
    // positioned child.
    _initTermTooltip() {
      const tip = document.getElementById('term-tip');
      if (!tip) return;
      const nameEl = tip.querySelector('.term-tip-name');
      const defEl = tip.querySelector('.term-tip-def');
      const hide = () => { if (!tip.hidden) tip.hidden = true; };
      document.addEventListener('pointerover', (event) => {
        const pill = event.target.closest('.has-term-tip[data-term-id]');
        if (!pill) { return; }
        const term = termsById.get(pill.dataset.termId);
        if (!term) { return; }
        nameEl.textContent = term.canonical;
        const def = term.definition_html || '';
        // innerHTML because a definition carries inline markup. Safe not
        // because the source is trusted, but because render_inline_markdown
        // escapes the text first and only re-admits <br>/<code>/<strong>/<em>,
        // none of which take attributes. Keep that invariant.
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
        const pill = event.target.closest('.has-term-tip[data-term-id]');
        if (!pill) return;
        if (event.relatedTarget && pill.contains(event.relatedTarget)) return;
        hide();
      });
      // Tooltip is positioned in viewport coords; any scroll invalidates it.
      window.addEventListener('scroll', hide, { capture: true, passive: true });
    },
    _readHash() {
      // Applying state from the hash must not itself write the hash (which
      // would create bogus history entries on back/forward).
      this._suppressHashWrite = true;
      const params = parseHash();
      // One parameter per selected key, not a joined list: a tag is free text
      // and may itself hold any separator.
      this.tagFilters = params.getAll('tag').filter(Boolean);
      if (params.has('module')) this.moduleFilter = params.get('module');
      else this.moduleFilter = null;
      this.termFilters = params.getAll('term-filter').filter(Boolean);
      if (params.has('sentence-filter')) this.sentenceFilter = params.get('sentence-filter');
      else this.sentenceFilter = null;
      if (params.has('status')) {
        const shown = new Set(params.get('status').split(',').filter(Boolean));
        this.shownStatuses = Object.fromEntries(STATUSES.map(s => [s, shown.has(s)]));
      } else {
        this.shownStatuses = allStatusesShown();
      }
      if (params.has('q')) this.search = params.get('q');
      else this.search = '';
      this.mainView = deserializeView(params);
      this.selectedStory = deserializeStory(params);
      // Derived, so a pasted `#sentence-filter=` link lands the way the in-app
      // jump does — lit on the sentence it names — and back/forward never
      // keeps a highlight from the state it left.
      this.highlightedSentences = this.sentenceFilter
        ? { [this.sentenceFilter.split(':')[1]]: true }
        : {};
      // The axis is ephemeral, but a link arriving with a filter should reveal
      // it. Only ever set, never reset — stepping back to an unfiltered state
      // must not yank the sidebar out from under the reader.
      if (this.termFilters.length && hasGlossary) this.view = 'terms';
      else if (this.tagFilters.length) this.view = 'tags';
      else if (this.moduleFilter) this.view = 'modules';
      const targetSlug = params.get('scenario');
      const targetScenario = targetSlug
        ? lookup(window.__REPORT_DATA__.scenario_slugs || {}, targetSlug, null)
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
      for (const tag of this.tagFilters) params.append('tag', tag);
      if (this.moduleFilter) params.set('module', this.moduleFilter);
      for (const termId of this.termFilters) params.append('term-filter', termId);
      if (this.sentenceFilter) params.set('sentence-filter', this.sentenceFilter);

      const shownInReport = statusesPresent.filter(s => this.shownStatuses[s]);
      if (shownInReport.length !== statusesPresent.length) {
        params.set('status', shownInReport.join(','));
      }

      if (this.search) params.set('q', this.search);
      serializeHash(params, mode);
    },
  };
}
