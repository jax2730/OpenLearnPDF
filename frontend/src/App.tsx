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
    <main>
      <h1>RTR4 学习系统</h1>
      <div style={{ display: "grid", gap: 24, gridTemplateColumns: "minmax(0, 1fr) minmax(320px, 0.8fr)" }}>
        <PdfReader
          bookId="rtr4-cn"
          chapter={5}
          page={page}
          selectedBlockId={selectedBlockId}
          onSelectBlock={setSelectedBlockId}
        />
        <div>
          <nav aria-label="第五章课程">
            <button type="button" onClick={() => setSectionSlug("section-5.1")}>
              5.1 着色模型
            </button>
            <button type="button" onClick={() => setSectionSlug("section-5.2")}>
              5.2 光源
            </button>
            <button
              type="button"
              onClick={() => setSectionSlug("section-5.2.2")}
            >
              5.2.2 精确光源
            </button>
          </nav>
          <LessonPanel
            chapterSlug="chapter-05"
            sectionSlug={sectionSlug}
            onNavigateSource={navigateSource}
          />
          <QuestionPanel onNavigateSource={navigateSource} />
        </div>
      </div>
    </main>
  );
}
