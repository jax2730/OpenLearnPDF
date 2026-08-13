import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import App from "./App";

vi.mock("./components/PdfReader", () => ({
  PdfReader: ({
    page,
    selectedBlockId,
  }: {
    page: number;
    selectedBlockId?: string;
  }) => (
    <div aria-label="PDF 阅读器">
      {page}:{selectedBlockId ?? "none"}
    </div>
  ),
}));

vi.mock("./components/LessonPanel", () => ({
  LessonPanel: ({
    onNavigateSource,
    sectionSlug,
  }: {
    onNavigateSource: (page: number, blockId: string) => void;
    sectionSlug: string;
  }) => (
    <div>
      <span aria-label="当前课程">{sectionSlug}</span>
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
});
