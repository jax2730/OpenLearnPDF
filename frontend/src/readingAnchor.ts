export function restoreAnchor(ratio: number, top: number, height: number, inset: number, maxScroll: number) {
  // A negative anchor denotes the top of the scroll container, including toolbar space.
  if (ratio < 0) return 0;
  return Math.max(0, Math.min(maxScroll, top + Math.max(0, Math.min(1, ratio)) * height - inset));
}
