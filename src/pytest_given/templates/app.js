function reportApp() {
  const data = window.__REPORT_DATA__;
  return {
    search: '',
    view: 'tags',
    showPassed: true,
    showFailed: true,
    showSkipped: true,
    expandedGroups: {},
    expandedSteps: {},
    expandedAttachments: {},
    expandedScenarios: {},
    activeTag: null,
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
      return parts.length ? parts.join(' · ') : 'All Scenarios';
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
    init() {
      this._readHash();
      ['search', 'activeTag', 'showPassed', 'showFailed', 'showSkipped'].forEach(key => {
        this.$watch(key, () => this._writeHash());
      });
      window.addEventListener('hashchange', () => this._readHash());
    },
    _readHash() {
      const params = new URLSearchParams(window.location.hash.slice(1));
      if (params.has('tag')) this.activeTag = params.get('tag');
      else this.activeTag = null;
      if (params.has('passed')) this.showPassed = params.get('passed') !== '0';
      if (params.has('failed')) this.showFailed = params.get('failed') !== '0';
      if (params.has('skipped')) this.showSkipped = params.get('skipped') !== '0';
      if (params.has('q')) this.search = params.get('q');
      else this.search = '';
    },
    _writeHash() {
      const params = new URLSearchParams();
      if (this.activeTag) params.set('tag', this.activeTag);
      if (!this.showPassed) params.set('passed', '0');
      if (!this.showFailed) params.set('failed', '0');
      if (!this.showSkipped) params.set('skipped', '0');
      if (this.search) params.set('q', this.search);
      const hash = params.toString();
      history.replaceState(null, '', hash ? '#' + hash : window.location.pathname);
    },
  };
}
