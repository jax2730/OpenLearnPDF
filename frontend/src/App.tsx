import { useState } from "react";

import { LessonPanel } from "./components/LessonPanel";
import { PdfReader } from "./components/PdfReader";

export default function App() {
  const [page, setPage] = useState(105);
  const [selectedBlockId, setSelectedBlockId] = useState<string>();

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
        <LessonPanel
          chapterSlug="chapter-05"
          sectionSlug="section-5.1"
          onNavigateSource={navigateSource}
        />
      </div>
    </main>
  );
}
