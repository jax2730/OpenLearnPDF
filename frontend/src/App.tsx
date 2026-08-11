import { useState } from "react";

import { PdfReader } from "./components/PdfReader";

export default function App() {
  const [selectedBlockId, setSelectedBlockId] = useState<string>();

  return (
    <main>
      <h1>RTR4 学习系统</h1>
      <PdfReader
        bookId="rtr4-cn"
        chapter={5}
        page={105}
        selectedBlockId={selectedBlockId}
        onSelectBlock={setSelectedBlockId}
      />
    </main>
  );
}
