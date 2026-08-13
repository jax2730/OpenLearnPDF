import { useState } from "react";

import { LessonPanel } from "./components/LessonPanel";
import { PdfReader } from "./components/PdfReader";
import { QuestionPanel } from "./components/QuestionPanel";

export default function App() {
  const [page, setPage] = useState(105);
  const [selectedBlockId, setSelectedBlockId] = useState<string>();
  const [sectionSlug, setSectionSlug] = useState("section-5.1");

  const navigateSource = (sourcePage: number, blockId: string) => {
    setPage(sourcePage);
    setSelectedBlockId(blockId);
  };

  return (
    <main className="app-shell">
      <header className="app-header">
        <h1>RTR4 学习系统 · 知识点精读</h1>
        <p>原书与讲解同步定位</p>
      </header>
      <div className="learning-workspace">
        <section aria-label="原书 PDF" className="workspace-pane source-pane">
          <header className="pane-header"><h2>原书 PDF · 第 {page} 页</h2></header>
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
              <button aria-pressed={sectionSlug === "section-5.1"} type="button" onClick={() => setSectionSlug("section-5.1")}>
              5.1 着色模型
              </button>
              <button aria-pressed={sectionSlug === "section-5.2"} type="button" onClick={() => setSectionSlug("section-5.2")}>
              5.2 光源
              </button>
              <button aria-pressed={sectionSlug === "section-5.2.2"} type="button" onClick={() => setSectionSlug("section-5.2.2")}>
              5.2.2 精确光源
              </button>
            </nav>
          </header>
          <div className="study-content">
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
