import { useState } from "react";

import { LessonPanel } from "./components/LessonPanel";
import { PdfReader } from "./components/PdfReader";
import { QuestionPanel } from "./components/QuestionPanel";

export default function App() {
  const [page, setPage] = useState(105);
  const [selectedBlockId, setSelectedBlockId] = useState<string>();
  const [sectionSlug, setSectionSlug] = useState("section-5.1");
  const [pageDraft, setPageDraft] = useState("105");
  const [pageError, setPageError] = useState("");

  const changePage = (next: number) => {
    setPage(next);
    setPageDraft(String(next));
    setPageError("");
    setSelectedBlockId(undefined);
  };

  const selectCourse = (slug: string, startPage: number) => {
    setSectionSlug(slug);
    changePage(startPage);
  };

  const navigateSource = (sourcePage: number, blockId: string) => {
    changePage(sourcePage);
    setSelectedBlockId(blockId);
  };

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
              <p className="page-context">第五章 · PDF 页码 104–154（非书内印刷页码）</p>
            </div>
            <form className="page-controls" aria-label="PDF 页面导航" onSubmit={(event) => {
              event.preventDefault();
              const next = Number(pageDraft);
              if (!pageDraft.trim() || !Number.isInteger(next) || next < 104 || next > 154) {
                setPageError("请输入 104–154 之间的整数页码");
                return;
              }
              changePage(next);
            }}>
              <button type="button" disabled={page <= 104} onClick={() => changePage(page - 1)}>上一页</button>
              <label>PDF 页码 <input aria-label="PDF 页码" inputMode="numeric" value={pageDraft} onChange={(event) => setPageDraft(event.target.value)} /></label>
              <button type="submit">跳转</button>
              <button type="button" disabled={page >= 154} onClick={() => changePage(page + 1)}>下一页</button>
            </form>
          </header>
          {pageError ? <p role="alert" className="reader-notice">{pageError}</p> : null}
          <PdfReader
            bookId="rtr4-cn"
            chapter={5}
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
            <p className="study-guide">点击讲解中的来源可定位原书。手动翻页保留当前课程，方便对照；目前精讲覆盖 5.1、5.2 与 5.2.2。</p>
            <LessonPanel
              chapterSlug="chapter-05"
              sectionSlug={sectionSlug}
              selectedBlockId={selectedBlockId}
              onNavigateSource={navigateSource}
            />
            <QuestionPanel onNavigateSource={navigateSource} />
          </div>
        </section>
      </div>
    </main>
  );
}
