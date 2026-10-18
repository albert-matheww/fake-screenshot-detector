import "@testing-library/jest-dom/vitest";

// jsdom has no canvas implementation (getContext logs "not implemented").
// Demo-image rendering treats a null context as "no preview image".
HTMLCanvasElement.prototype.getContext = () => null;
