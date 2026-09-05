import "@testing-library/jest-dom/vitest";

// jsdom has no EventSource. The operation hook is exercised through a stub in
// the tests that need it rather than by pulling in a polyfill.
if (!("EventSource" in globalThis)) {
  (globalThis as unknown as { EventSource: unknown }).EventSource = class {
    close() {}
    addEventListener() {}
  };
}
