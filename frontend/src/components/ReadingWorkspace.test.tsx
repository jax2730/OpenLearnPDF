import { act, fireEvent, render, screen } from "@testing-library/react";
import { beforeEach, expect, it, vi } from "vitest";
import { ReadingWorkspace } from "./ReadingWorkspace";
import { restoreAnchor } from "../readingAnchor";

beforeEach(() => { localStorage.clear(); vi.restoreAllMocks(); });

it("collapses without removing the PDF or resetting study input", () => {
  render(<ReadingWorkspace source={<section><canvas data-testid="pdf" /></section>} study={<section><textarea aria-label="草稿" /><details><summary>推导</summary>解释</details></section>} />);
  const canvas = screen.getByTestId("pdf");
  fireEvent.change(screen.getByLabelText("草稿"), { target: { value: "问题" } });
  const detail = screen.getByText("推导").closest("details")!;
  detail.open = true;
  fireEvent.click(screen.getByRole("button", { name: "收起伴读" }));
  expect(screen.queryByRole("textbox")).not.toBeInTheDocument();
  expect(screen.getByTestId("pdf")).toBe(canvas);
  expect(screen.getByRole("button", { name: "展开伴读" })).toHaveFocus();
  fireEvent.click(screen.getByRole("button", { name: "展开伴读" }));
  expect(screen.getByLabelText("草稿")).toHaveValue("问题");
  expect(detail.open).toBe(true);
});

it("restores collapsed preference and tolerates unavailable storage", () => {
  localStorage.setItem("openlearn:workspace:v1", JSON.stringify({ sidebarOpen: false }));
  const view = render(<ReadingWorkspace source={<p>原书</p>} study={<p>讲解</p>} />);
  expect(screen.getByRole("button", { name: "展开伴读" })).toBeInTheDocument();
  vi.spyOn(Storage.prototype, "setItem").mockImplementation(() => { throw new Error("blocked"); });
  fireEvent.click(screen.getByRole("button", { name: "展开伴读" }));
  expect(screen.getByText("讲解")).toBeVisible();
  view.unmount();
});

it("keeps a normalized page anchor when width changes", () => {
  expect(restoreAnchor(0.5, 100, 1600, 50, 2000)).toBe(850);
  expect(restoreAnchor(1, 100, 1600, 50, 900)).toBe(900);
  expect(restoreAnchor(0, 0, 0, 50, 0)).toBe(0);
  expect(restoreAnchor(-1, 200, 1600, 50, 2000)).toBe(0);
});

it("falls back safely for corrupt or incorrectly typed preferences", () => {
  for (const value of ["broken", "null", '{"sidebarOpen":"false"}']) {
    localStorage.setItem("openlearn:workspace:v1", value);
    const view = render(<ReadingWorkspace source={<p>原书</p>} study={<p>讲解</p>} />);
    expect(screen.getByRole("button", { name: "收起伴读" })).toBeInTheDocument();
    view.unmount();
  }
});

it("resizes with keyboard and restores the default split", () => {
  render(<ReadingWorkspace source={<p>原书</p>} study={<p>讲解</p>} />);
  const separator = screen.getByRole("separator");
  expect(separator).toHaveAttribute("aria-valuenow", "40");
  fireEvent.keyDown(separator, { key: "ArrowLeft" });
  expect(separator).toHaveAttribute("aria-valuenow", "42");
  fireEvent.keyDown(separator, { key: "Home" });
  expect(separator).toHaveAttribute("aria-valuenow", "40");
});

it("shows only one compact pane without replacing mounted content", () => {
  let resize: ResizeObserverCallback = () => undefined;
  vi.stubGlobal("ResizeObserver", class {
    constructor(callback: ResizeObserverCallback) { resize = callback; }
    observe() {} disconnect() {}
  });
  const view = render(<ReadingWorkspace source={<canvas data-testid="original" />} study={<textarea aria-label="笔记" />} />);
  const original = screen.getByTestId("original");
  // Act through the observer: mode is based on actual workspace width.
  fireEvent(window, new Event("resize"));
  act(() => resize([{ contentRect: { width: 700 } } as ResizeObserverEntry], {} as ResizeObserver));
  fireEvent.click(screen.getByRole("button", { name: "伴读" }));
  expect(screen.getByTestId("original")).not.toBeVisible();
  expect(screen.getByLabelText("笔记")).toBeVisible();
  fireEvent.click(screen.getByRole("button", { name: "原书" }));
  expect(screen.getByTestId("original")).toBe(original);
  expect(screen.queryByRole("textbox")).not.toBeInTheDocument();
  view.unmount(); vi.unstubAllGlobals();
});
