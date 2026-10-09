import { useEffect, useRef, useState } from "react";
import { getBook, getCourses } from "./api";
import type { BookManifest } from "./types";
import { courseForPage, type CourseEntry } from "./courseCatalog";

import { LessonPanel } from "./components/LessonPanel";
import { PdfReader } from "./components/PdfReader";
import { QuestionPanel } from "./components/QuestionPanel";
import { ReadingWorkspace } from "./components/ReadingWorkspace";
import { RenderingGuide } from "./components/RenderingGuide";

export default function App() {
  const [page, setPage] = useState(105);
  const [selectedBlockId, setSelectedBlockId] = useState<string>();
  const [sectionSlug, setSectionSlug] = useState("section-5.1");
  const [pageDraft, setPageDraft] = useState("105");
  const [pageError, setPageError] = useState("");
  const [book, setBook] = useState<BookManifest>();
  const [bookError, setBookError] = useState("");
  const [courses, setCourses] = useState<CourseEntry[]>([]);
  const [courseError, setCourseError] = useState("");
  const [reload, setReload] = useState(0);
  const [guideOpen, setGuideOpen] = useState(false);
  const [sourceRequest, setSourceRequest] = useState(0);
  const [returnPage, setReturnPage] = useState<number>();
  const returnAnchor = useRef(-1);
  const [restorePosition, setRestorePosition] = useState<number>();
  const captureReturn = () => {
    if (returnPage !== undefined) return;
    const pane = document.querySelector<HTMLElement>(".source-pane");
    const canvas = pane?.querySelector("canvas");
    if (!pane || !canvas || canvas.clientHeight <= 0) { returnAnchor.current = -1; return; }
    const top = canvas.getBoundingClientRect().top - pane.getBoundingClientRect().top + pane.scrollTop;
    returnAnchor.current = pane.scrollTop === 0 ? -1 : Math.max(0, Math.min(1, (pane.scrollTop + (pane.querySelector<HTMLElement>(".source-toolbar")?.offsetHeight ?? 0) - top) / canvas.clientHeight));
  };

  useEffect(() => {
    const controller = new AbortController();
    setBookError("");
    setCourseError("");
    getCourses("rtr4-cn", controller.signal).then((data) => {
      if (!controller.signal.aborted) setCourses(data.courses);
    }).catch(() => { if (!controller.signal.aborted) setCourseError("课程目录加载失败，请重试"); });
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
  const activeCourse = courses.find((course) => course.section_slug === sectionSlug);
  const hasLesson = !!activeCourse && (returnPage !== undefined || activeCourse.source_pages.includes(page));

  const changePage = (next: number) => {
    setRestorePosition(undefined);
    setReturnPage(undefined);
    setPage(next);
    setPageDraft(String(next));
    setPageError("");
    setSelectedBlockId(undefined);
    const nextCourse = courseForPage(courses, next, sectionSlug);
    if (nextCourse) setSectionSlug(nextCourse.section_slug);
  };

  const selectCourse = (slug: string, startPage: number) => {
    setGuideOpen(false);
    changePage(startPage);
    setSectionSlug(slug);
  };

  const navigateSource = (sourcePage: number, blockId: string) => {
    captureReturn();
    changePage(sourcePage);
    setReturnPage(returnPage ?? page);
    setSourceRequest((current) => current + 1);
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
      <ReadingWorkspace sourceRequest={sourceRequest} source={
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
          {returnPage !== undefined ? <button type="button" className="return-source" onClick={() => { changePage(returnPage); setRestorePosition(returnAnchor.current); }}>返回引用前 · PDF {returnPage}（窄屏可切回伴读）</button> : null}
          <PdfReader
            bookId="rtr4-cn"
            page={page}
            restorePosition={restorePosition}
            selectedBlockId={selectedBlockId}
            onSelectBlock={setSelectedBlockId}
          />
        </section>
      } study={
        <section aria-label="知识点学习区" className="workspace-pane study-pane">
          <header className="pane-header">
            <button type="button" aria-pressed={guideOpen} onClick={() => setGuideOpen(!guideOpen)}>渲染流程入门</button>
            <details><summary>已发布课程目录</summary>
              <nav aria-label="已发布课程" className="course-selector">
                {courses.map((course) => <button key={course.id} aria-pressed={!guideOpen && sectionSlug === course.section_slug} type="button" onClick={() => selectCourse(course.section_slug, course.start_page)}>{course.section} {course.title}</button>)}
              </nav>
            </details>
          </header>
          <div className="study-content">
            <p className="study-guide">全书可阅读不代表全书已完成精讲。当前发布 {courses.length} 个课程及跨章入门伴读。</p>
            {courseError ? <p role="alert">{courseError}<button onClick={() => setReload((value) => value + 1)}>重新加载课程目录</button></p> : null}
            {guideOpen ? <RenderingGuide onNavigateSource={(target) => {
              captureReturn();
              const origin = returnPage ?? page;
              changePage(target); setReturnPage(origin); setSourceRequest((current) => current + 1);
            }} /> : hasLesson ? <LessonPanel
              chapterSlug={activeCourse!.chapter_slug}
              sectionSlug={sectionSlug}
              selectedBlockId={selectedBlockId}
              onNavigateSource={navigateSource}
            /> : <p role="status">本页暂无已发布精讲，可继续阅读原书或选择已有课程。</p>}
            {chapter?.id === "5" && !guideOpen ? <details><summary>查找相关内容（目前仅第五章）</summary><QuestionPanel onNavigateSource={navigateSource} /></details> : null}
          </div>
        </section>
      } />
    </main>
  );
}
