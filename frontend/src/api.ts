import type {
  BookManifest,
  LessonBundle,
  PageDocument,
  QuestionAnswer,
  SourceBlock,
} from "./types";

export function getBook(bookId: string, signal?: AbortSignal) {
  return readJson<BookManifest>(`/api/books/${encodeURIComponent(bookId)}`, signal);
}

export function getBookPage(bookId: string, page: number, signal?: AbortSignal) {
  return readJson<PageDocument>(`/api/books/${encodeURIComponent(bookId)}/pages/${page}`, signal);
}

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

export function getBlock(blockId: string, signal?: AbortSignal) {
  return readJson<SourceBlock>(
    `/api/blocks/${encodeURIComponent(blockId)}`,
    signal,
  );
}

export function getLesson(
  chapterSlug: string,
  sectionSlug: string,
  signal?: AbortSignal,
) {
  return readJson<LessonBundle>(
    `/api/lessons/${encodeURIComponent(chapterSlug)}/${encodeURIComponent(sectionSlug)}`,
    signal,
  );
}

export async function askQuestion(
  question: string,
  signal?: AbortSignal,
): Promise<QuestionAnswer> {
  const response = await fetch("/api/questions", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ question, chapter: 5, book_id: "rtr4-cn" }),
    signal,
  });
  if (!response.ok) {
    throw new Error(`请求失败 (${response.status})`);
  }
  return (await response.json()) as QuestionAnswer;
}
