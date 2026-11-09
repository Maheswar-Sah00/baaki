// One object URL per Blob, cached, so re-renders (and React StrictMode's
// double effects) never hand a revoked URL to an <audio> element.
const cache = new WeakMap<Blob, string>();

export function blobUrl(blob: Blob): string {
  let url = cache.get(blob);
  if (!url) {
    url = URL.createObjectURL(blob);
    cache.set(blob, url);
  }
  return url;
}

export function revokeBlobUrl(blob: Blob): void {
  const url = cache.get(blob);
  if (url) {
    URL.revokeObjectURL(url);
    cache.delete(blob);
  }
}
