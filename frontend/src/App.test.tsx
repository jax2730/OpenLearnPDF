import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import App from "./App";

vi.mock("./api", () => ({ getBook: vi.fn().mockResolvedValue({
  id: "rtr4-cn", title: "RTR4", page_count: 903,
  chapters: [{ id: "5", title: "第五章", start_page: 104, end_page: 154 }],
}) }));

async function openApp() {
  render(<App />);
  await screen.findByLabelText("PDF 页码");
}

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
  it("opens the cross-chapter guide and returns from a cited PDF page", async () => {
    await openApp();
    fireEvent.click(screen.getByRole("button", { name: "渲染流程入门" }));
    fireEvent.click(screen.getByRole("button", { name: "20.1 延迟着色 · PDF 708" }));
    expect(screen.getByLabelText("PDF 页码")).toHaveValue("708");
    expect(screen.getByRole("heading", { name: "前向、延迟与后处理：从一帧的产生开始" })).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: /返回引用前/ }));
    expect(screen.getByLabelText("PDF 页码")).toHaveValue("105");
  });
  it("commits a page only on submit and rejects invalid pages", async () => {
    await openApp();
    const input = screen.getByLabelText("PDF 页码");
    fireEvent.change(input, { target: { value: "904" } });
    expect(screen.getByLabelText("PDF 阅读器")).toHaveTextContent("105:none");
    fireEvent.click(screen.getByRole("button", { name: "跳转" }));
    expect(screen.getByRole("alert")).toHaveTextContent("1–903");
    fireEvent.change(input, { target: { value: "903" } });
    fireEvent.click(screen.getByRole("button", { name: "跳转" }));
    expect(screen.getByLabelText("PDF 阅读器")).toHaveTextContent("903:none");
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: "下一页" })).toBeDisabled();
    fireEvent.change(input, { target: { value: "1" } });
    fireEvent.click(screen.getByRole("button", { name: "跳转" }));
    expect(screen.getByRole("button", { name: "上一页" })).toBeDisabled();
  });

  it("clears stale citations when changing course or browsing pages", async () => {
    await openApp();
    fireEvent.click(screen.getByRole("button", { name: "跳到来源" }));
    expect(screen.getByLabelText("PDF 页码")).toHaveValue("106");
    fireEvent.click(screen.getByRole("button", { name: "下一页" }));
    expect(screen.getByLabelText("PDF 阅读器")).toHaveTextContent("107:none");
    fireEvent.click(screen.getByRole("button", { name: "5.2.2 精确光源" }));
    expect(screen.getByLabelText("PDF 阅读器")).toHaveTextContent("109:none");
    expect(screen.getByLabelText("PDF 页码")).toHaveValue("109");
  });

  it("shows the RTR4 learning system heading", async () => {
    await openApp();

    expect(
      screen.getByRole("heading", { name: /RTR4 学习系统/ }),
    ).toBeInTheDocument();
  });

  it("renders independently from previous tests", async () => {
    await openApp();

    expect(
      screen.getByRole("heading", { name: /RTR4 学习系统/ }),
    ).toBeInTheDocument();
  });

  it("navigates the reader and highlights a lesson citation", async () => {
    await openApp();

    fireEvent.click(screen.getByRole("button", { name: "跳到来源" }));

    expect(screen.getByLabelText("PDF 阅读器")).toHaveTextContent(
      "106:p106-formula-5.2",
    );
  });

  it("switches between chapter 5 lessons", async () => {
    await openApp();

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

  it("forwards a selected PDF block to the lesson", async () => {
    await openApp();

    fireEvent.click(screen.getByRole("button", { name: "选择 PDF 块" }));
    expect(screen.getByLabelText("课程选中来源")).toHaveTextContent(
      "p111-formula-5.11",
    );
  });

  it("renders labelled source and study panes", async () => {
    await openApp();

    expect(screen.getByRole("region", { name: "原书 PDF" })).toHaveClass(
      "workspace-pane",
      "source-pane",
    );
    expect(screen.getByRole("region", { name: "知识点学习区" })).toHaveClass(
      "workspace-pane",
      "study-pane",
    );
    expect(screen.getByRole("navigation", { name: "第五章课程" })).toHaveClass(
      "course-selector",
    );
  });
});
