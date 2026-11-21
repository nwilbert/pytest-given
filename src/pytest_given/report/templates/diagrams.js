// The diagrams page's Alpine component: the story switcher, step-through
// replay, zoom and pan, and the term tooltips. The data is
// window.__DIAGRAMS_DATA__, which renderer.py fills in.
const diagramsData = window.__DIAGRAMS_DATA__;
const diagramsTheme = window.__REPORT_THEME__;

function storyFromHash() {
  let hash;
  try { hash = decodeURIComponent(location.hash.slice(1)); } catch { hash = ''; }
  return diagramsData.story_ids.includes(hash) ? hash : null;
}

function diagramsApp() {
  return {
    selectedStory: null,
    step: null,
    hoverSentence: null,
    tooltip: null,
    zoom: 1,
    panX: 0,
    panY: 0,
    dragging: false,
    lastX: 0,
    lastY: 0,
    maxSteps: diagramsData.max_steps,
    themeChoice: diagramsTheme.choice,

    init() {
      this.selectedStory = storyFromHash() || diagramsData.story_ids[0] || null;
      this.$watch('selectedStory', (id) => {
        history.replaceState(null, '', '#' + encodeURIComponent(id));
        this.step = null;
        this.hoverSentence = null;
        this.$nextTick(() => this.fitDiagram());
      });
      window.addEventListener('hashchange', () => {
        const next = storyFromHash();
        if (next) this.selectedStory = next;
      });
      window.addEventListener('keydown', (event) => {
        if (event.key === 'ArrowRight') this.nextStep();
        if (event.key === 'ArrowLeft') this.prevStep();
      });
      this.$nextTick(() => this.fitDiagram());
    },

    setTheme(choice) {
      this.themeChoice = choice;
      diagramsTheme.set(choice);
    },

    nextStep() {
      const max = this.maxSteps[this.selectedStory];
      if (max > 0) this.step = this.step === null ? 1 : Math.min(this.step + 1, max);
    },
    prevStep() {
      if (this.step !== null) this.step = this.step <= 1 ? null : this.step - 1;
    },
    faded(number) { return this.step !== null && number > this.step; },

    surfaceStyle() {
      return 'transform: translate(' + this.panX + 'px,' + this.panY +
             'px) scale(' + this.zoom + '); transform-origin: 0 0;';
    },
    canvas() {
      return document.querySelector(
        '[data-canvas="' + CSS.escape(this.selectedStory) + '"]'
      );
    },
    // Zoom toward (cx, cy) in canvas coordinates: the pan keeps that point
    // where it is.
    setZoom(next, cx, cy) {
      next = Math.min(4, Math.max(0.1, next));
      const ratio = next / this.zoom;
      this.panX = cx - (cx - this.panX) * ratio;
      this.panY = cy - (cy - this.panY) * ratio;
      this.zoom = next;
    },
    viewportCenter() {
      const canvas = this.canvas();
      return canvas ? [canvas.clientWidth / 2, canvas.clientHeight / 2] : [0, 0];
    },
    zoomIn() { const [cx, cy] = this.viewportCenter(); this.setZoom(this.zoom * 1.2, cx, cy); },
    zoomOut() { const [cx, cy] = this.viewportCenter(); this.setZoom(this.zoom / 1.2, cx, cy); },
    resetZoom() { this.zoom = 1; this.panX = 0; this.panY = 0; },
    fitDiagram() {
      const canvas = this.canvas();
      const size = diagramsData.diagram_sizes[this.selectedStory];
      if (!canvas || !size) { this.resetZoom(); return; }
      // A section shown this frame may not have a size yet, and fitting into
      // a zero-sized box would scale the diagram to nothing.
      if (!canvas.clientWidth || !canvas.clientHeight) {
        requestAnimationFrame(() => this.fitDiagram());
        return;
      }
      const [width, height] = size;
      const scale = Math.min(canvas.clientWidth / width, canvas.clientHeight / height, 1) * 0.95;
      this.zoom = scale;
      this.panX = (canvas.clientWidth - width * scale) / 2;
      this.panY = (canvas.clientHeight - height * scale) / 2;
    },
    // The wheel zooms toward the cursor; a trackpad pinch or ctrl/cmd + wheel
    // sends smaller deltas, so it gets a larger factor per tick. Dragging pans.
    onWheel(event) {
      const rect = this.canvas().getBoundingClientRect();
      const rate = (event.ctrlKey || event.metaKey) ? 0.01 : 0.0015;
      this.setZoom(
        this.zoom * Math.exp(-event.deltaY * rate),
        event.clientX - rect.left,
        event.clientY - rect.top,
      );
    },
    // Pointer capture keeps a drag going when the cursor leaves the canvas.
    onPointerDown(event) {
      if (event.button !== 0) return;
      this.dragging = true;
      this.lastX = event.clientX;
      this.lastY = event.clientY;
      event.currentTarget.setPointerCapture(event.pointerId);
    },
    onPointerMove(event) {
      if (!this.dragging) return;
      this.panX += event.clientX - this.lastX;
      this.panY += event.clientY - this.lastY;
      this.lastX = event.clientX;
      this.lastY = event.clientY;
    },
    onPointerUp(event) {
      if (!this.dragging) return;
      this.dragging = false;
      if (event.currentTarget.hasPointerCapture(event.pointerId)) {
        event.currentTarget.releasePointerCapture(event.pointerId);
      }
    },

    showTip(event, title, termId) {
      this.tooltip = {
        x: event.clientX,
        y: event.clientY,
        title: title,
        definition: termId ? diagramsData.term_definitions[termId] : null,
      };
    },
  };
}
