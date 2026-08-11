import type { PageDocument } from "./types";

async function readJson<T>(url: string, signal?: AbortSignal): Promise<T> {
  const response = await fetch(url, { signal });
  if (!response.ok) {
    throw new Error(`请求失败 (${response.status})`);
  }
  return (await response.json()) as T;
}

export function getPage(
  bookId: string,
  chapter: number,
  page: number,
  signal?: AbortSignal,
): Promise<PageDocument> {
  return readJson<PageDocument>(
    `/api/books/${encodeURIComponent(bookId)}/chapters/${chapter}/pages/${page}`,
    signal,
  );
}
