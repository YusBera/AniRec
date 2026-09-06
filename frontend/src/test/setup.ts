import "@testing-library/jest-dom/vitest";

// Minimal dialog lifecycle for component tests. Native focus containment and
// Escape must still be exercised in a real browser, not inferred from jsdom.
if (!HTMLDialogElement.prototype.showModal) {
  HTMLDialogElement.prototype.showModal = function () { this.open = true; };
  HTMLDialogElement.prototype.close = function () {
    if (!this.open) return;
    this.open = false;
    queueMicrotask(() => this.dispatchEvent(new Event("close")));
  };
}

// jsdom has no EventSource. The operation hook is exercised through a stub in
// the tests that need it rather than by pulling in a polyfill.
if (!("EventSource" in globalThis)) {
  (globalThis as unknown as { EventSource: unknown }).EventSource = class {
    close() {}
    addEventListener() {}
  };
}
