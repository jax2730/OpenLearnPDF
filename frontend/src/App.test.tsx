import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import App from "./App";

vi.mock("./components/PdfReader", () => ({
  PdfReader: ({
    page,
    selectedBlockId,
    onSelectBlock,
  }: {
    page: number;
    selectedBlockId?: string;
    onSelectBlock: (blockId: string) => void;
  }) => (
    <div aria-label="PDF 阅读器">
      {page}:{selectedBlockId ?? "none"}
      <button onClick={() => onSelectBlock("p111-formula-5.11")}>选择 PDF 块</button>
    </div>
  ),
}));

vi.mock("./components/LessonPanel", () => ({
  LessonPanel: ({
    onNavigateSource,
    sectionSlug,
    selectedBlockId,
  }: {
    onNavigateSource: (page: number, blockId: string) => void;
    sectionSlug: string;
    selectedBlockId?: string;
  }) => (
    <div>
      <span aria-label="当前课程">{sectionSlug}</span>
      <span aria-label="课程选中来源">{selectedBlockId ?? "none"}</span>
      <button onClick={() => onNavigateSource(106, "p106-formula-5.2")}>
        跳到来源
      </button>
    </div>
  ),
}));

describe("App", () => {
  it("shows the RTR4 learning system heading", () => {
    render(<App />);

    expect(
      screen.getByRole("heading", { name: /RTR4 学习系统/ }),
    ).toBeInTheDocument();
  });

  it("renders independently from previous tests", () => {
    render(<App />);

    expect(
      screen.getByRole("heading", { name: /RTR4 学习系统/ }),
    ).toBeInTheDocument();
  });

  it("navigates the reader and highlights a lesson citation", () => {
    render(<App />);

    fireEvent.click(screen.getByRole("button", { name: "跳到来源" }));

    expect(screen.getByLabelText("PDF 阅读器")).toHaveTextContent(
      "106:p106-formula-5.2",
    );
  });

  it("switches between chapter 5 lessons", () => {
    render(<App />);

    expect(screen.getByLabelText("当前课程")).toHaveTextContent("section-5.1");
    fireEvent.click(screen.getByRole("button", { name: "5.2 光源" }));
    expect(screen.getByLabelText("当前课程")).toHaveTextContent("section-5.2");
    fireEvent.click(screen.getByRole("button", { name: "5.1 着色模型" }));
    expect(screen.getByLabelText("当前课程")).toHaveTextContent("section-5.1");

    fireEvent.click(screen.getByRole("button", { name: "5.2.2 精确光源" }));
    expect(screen.getByLabelText("当前课程")).toHaveTextContent(
      "section-5.2.2",
    );
  });

  it("forwards a selected PDF block to the lesson", () => {
    render(<App />);

    fireEvent.click(screen.getByRole("button", { name: "选择 PDF 块" }));
    expect(screen.getByLabelText("课程选中来源")).toHaveTextContent(
      "p111-formula-5.11",
    );
  });
});
