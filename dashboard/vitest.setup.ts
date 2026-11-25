import "@testing-library/jest-dom";
window.scrollTo = () => {};
Object.defineProperty(window, "matchMedia", {writable: true, value: (query: string) => ({matches: true, media: query, addEventListener() {}, removeEventListener() {}, addListener() {}, removeListener() {}, dispatchEvent() { return false; }})});
