import { useEffect, useState } from "react";
import { getBook } from "./api";
import type { BookManifest } from "./types";

import { LessonPanel } from "./components/LessonPanel";
import { PdfReader } from "./components/PdfReader";
import { QuestionPanel } from "./components/QuestionPanel";

export default function App() {
  const [page, setPage] = useState(105);
  const [selectedBlockId, setSelectedBlockId] = useState<string>();
  const [sectionSlug, setSectionSlug] = useState("section-5.1");
  const [pageDraft, setPageDraft] = useState("105");
  const [pageError, setPageError] = useState("");
  const [book, setBook] = useState<BookManifest>();
  const [bookError, setBookError] = useState("");
  const [reload, setReload] = useState(0);

  useEffect(() => {
    const controller = new AbortController();
    setBookError("");
    getBook("rtr4-cn", controller.signal).then((data) => {
      if (controller.signal.aborted) return;
      setBook(data);
      setPage((current) => Math.min(current, data.page_count));
      setPageDraft((current) => String(Math.min(Number(current), data.page_count)));
    }).catch((error: unknown) => {
      if (!controller.signal.aborted) setBookError(error instanceof Error ? error.message : "书籍不可用");
    });
    return () => controller.abort();
  }, [reload]);
  const chapter = book?.chapters.find((item) => page >= item.start_page && page <= item.end_page);
  // Temporary compatibility boundary for the existing authored lessons.
  // The next catalog migration will derive these associations from source blocks.
  const hasLesson = page >= 105 && page <= 114;

  const changePage = (next: number) => {
    setPage(next);
    setPageDraft(String(next));
    setPageError("");
    setSelectedBlockId(undefined);
    if (next >= 105 && next <= 114) {
      setSectionSlug(next >= 109 ? "section-5.2.2" : next >= 107 ? "section-5.2" : "section-5.1");
    }
  };

  const selectCourse = (slug: string, startPage: number) => {
    changePage(startPage);
    setSectionSlug(slug);
  };

  const navigateSource = (sourcePage: number, blockId: string) => {
    changePage(sourcePage);
    setSectionSlug(sectionSlug);
    setSelectedBlockId(blockId);
  };

  if (!book) return <main className="app-shell"><h1>RTR4 学习系统</h1>
    {bookError ? <><p role="alert">书籍加载失败：{bookError}</p><button onClick={() => setReload((value) => value + 1)}>重试</button></> : <p role="status">正在加载书籍目录…</p>}
  </main>;

  return (
    <main className="app-shell">
      <header className="app-header">
        <h1>RTR4 学习系统 · 知识点精读</h1>
        <p>先读原书，再看讲解，最后动手验证</p>
      </header>
      <div className="learning-workspace">
        <section aria-label="原书 PDF" className="workspace-pane source-pane">
          <header className="pane-header source-toolbar">
            <div>
              <h2>原书 PDF · 第 {page} 页</h2>
              <p className="page-context">全书共 {book.page_count} 页 · {chapter?.title ?? "未登记章节区域"} · PDF 页码（非书内印刷页码）</p>
              <details><summary>书籍目录</summary>
                <p>目录仅显示已登记章节；其他页面可通过页码直接阅读。</p>
                <nav aria-label="已登记章节">{book.chapters.map((item) => <button key={item.id} type="button" onClick={() => changePage(item.start_page)}>{item.title} · PDF {item.start_page}–{item.end_page}</button>)}</nav>
              </details>
            </div>
            <form className="page-controls" aria-label="PDF 页面导航" onSubmit={(event) => {
              event.preventDefault();
              const next = Number(pageDraft);
              if (!pageDraft.trim() || !Number.isInteger(next) || next < 1 || next > book.page_count) {
                setPageError(`请输入 1–${book.page_count} 之间的整数页码`);
                return;
              }
              changePage(next);
            }}>
              <button type="button" disabled={page <= 1} onClick={() => changePage(page - 1)}>上一页</button>
              <label>PDF 页码 <input aria-label="PDF 页码" inputMode="numeric" value={pageDraft} onChange={(event) => setPageDraft(event.target.value)} /></label>
              <button type="submit">跳转</button>
              <button type="button" disabled={page >= book.page_count} onClick={() => changePage(page + 1)}>下一页</button>
            </form>
          </header>
          {pageError ? <p role="alert" className="reader-notice">{pageError}</p> : null}
          <PdfReader
            bookId="rtr4-cn"
            page={page}
            selectedBlockId={selectedBlockId}
            onSelectBlock={setSelectedBlockId}
          />
        </section>
        <section aria-label="知识点学习区" className="workspace-pane study-pane">
          <header className="pane-header">
            <nav aria-label="第五章课程" className="course-selector">
              <button aria-pressed={sectionSlug === "section-5.1"} type="button" onClick={() => selectCourse("section-5.1", 105)}>
              5.1 着色模型
              </button>
              <button aria-pressed={sectionSlug === "section-5.2"} type="button" onClick={() => selectCourse("section-5.2", 106)}>
              5.2 光源
              </button>
              <button aria-pressed={sectionSlug === "section-5.2.2"} type="button" onClick={() => selectCourse("section-5.2.2", 109)}>
              5.2.2 精确光源
              </button>
            </nav>
          </header>
          <div className="study-content">
            <p className="study-guide">全书可阅读不代表全书已完成精讲。现有课程入口：5.1、5.2 与 5.2.2。</p>
            {hasLesson ? <LessonPanel
              chapterSlug="chapter-05"
              sectionSlug={sectionSlug}
              selectedBlockId={selectedBlockId}
              onNavigateSource={navigateSource}
            /> : <p role="status">本页暂无已发布精讲，可继续阅读原书或选择已有课程。</p>}
            {chapter?.id === "5" ? <QuestionPanel onNavigateSource={navigateSource} /> : <p>本区域暂未接入来源检索。</p>}
          </div>
        </section>
      </div>
    </main>
  );
}
