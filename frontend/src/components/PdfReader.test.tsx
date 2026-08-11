import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { PdfReader } from "./PdfReader";

const { getPage, getDocument } = vi.hoisted(() => ({
  getPage: vi.fn(),
  getDocument: vi.fn(),
}));

vi.mock("pdfjs-dist", () => ({
  GlobalWorkerOptions: { workerSrc: "" },
  getDocument,
}));

vi.mock("pdfjs-dist/build/pdf.worker.min.mjs?url", () => ({
  default: "/pdf.worker.min.mjs",
}));

const page = {
  page: 105,
  width_points: 595,
  height_points: 842,
  blocks: [
    {
      id: "p105-formula-5.1",
      type: "formula",
      page: 105,
      bbox: { x0: 0.1, y0: 0.5, x1: 0.9, y1: 0.6 },
      latex: "c_{shaded}",
      number: "5.1",
      relations: [],
      source: { parser: "mineru", version: "2", confidence: 0.99 },
    },
  ],
};

describe("PdfReader", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({ ok: true, json: async () => page }),
    );
    vi.spyOn(HTMLCanvasElement.prototype, "getContext").mockReturnValue(
      {} as CanvasRenderingContext2D,
    );
    getPage.mockResolvedValue({
      getViewport: ({ scale }: { scale: number }) => ({
        width: 595 * scale,
        height: 842 * scale,
      }),
      render: () => ({ promise: Promise.resolve(), cancel: vi.fn() }),
    });
    getDocument.mockReturnValue({
      promise: Promise.resolve({ getPage }),
      destroy: vi.fn(),
    });
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("requests page 105 and selects its formula overlay", async () => {
    const onSelectBlock = vi.fn();

    render(
      <PdfReader
        bookId="rtr4-cn"
        chapter={5}
        page={105}
        onSelectBlock={onSelectBlock}
      />,
    );

    const overlay = await screen.findByRole("button", {
      name: "公式 5.1，第 105 页",
    });
    expect(fetch).toHaveBeenCalledWith(
      "/api/books/rtr4-cn/chapters/5/pages/105",
      expect.objectContaining({ signal: expect.any(AbortSignal) }),
    );
    expect(getDocument).toHaveBeenCalledWith({
      url: "/api/books/rtr4-cn/source",
    });

    fireEvent.click(overlay);
    expect(onSelectBlock).toHaveBeenCalledWith("p105-formula-5.1");
  });

  it("uses normalized percentages and marks the selected overlay", async () => {
    render(
      <PdfReader
        bookId="rtr4-cn"
        chapter={5}
        page={105}
        selectedBlockId="p105-formula-5.1"
        onSelectBlock={() => undefined}
      />,
    );

    const overlay = await screen.findByRole("button", {
      name: "公式 5.1，第 105 页",
    });
    expect(overlay).toHaveStyle({
      left: "10%",
      top: "50%",
      width: "80%",
      height: "10%",
    });
    expect(overlay).toHaveAttribute("aria-pressed", "true");
  });

  it("shows a visible PDF load error", async () => {
    getDocument.mockReturnValue({
      promise: Promise.reject(new Error("broken PDF")),
      destroy: vi.fn(),
    });

    render(
      <PdfReader
        bookId="rtr4-cn"
        chapter={5}
        page={105}
        onSelectBlock={() => undefined}
      />,
    );

    await waitFor(() => {
      expect(screen.getByRole("alert")).toHaveTextContent(
        "PDF 页面加载失败：broken PDF",
      );
    });
  });

  it("serializes resize rendering on the same canvas", async () => {
    let notifyResize: () => void = () => undefined;
    vi.stubGlobal(
      "ResizeObserver",
      class {
        constructor(callback: ResizeObserverCallback) {
          notifyResize = () => callback([], this as unknown as ResizeObserver);
        }
        observe() {}
        disconnect() {}
        unobserve() {}
      },
    );
    let finishFirst: () => void = () => undefined;
    const firstRender = new Promise<void>((resolve) => {
      finishFirst = resolve;
    });
    const renderPage = vi
      .fn()
      .mockReturnValueOnce({ promise: firstRender, cancel: vi.fn() })
      .mockReturnValue({ promise: Promise.resolve(), cancel: vi.fn() });
    getPage.mockResolvedValue({
      getViewport: ({ scale }: { scale: number }) => ({
        width: 595 * scale,
        height: 842 * scale,
      }),
      render: renderPage,
    });

    render(
      <PdfReader
        bookId="rtr4-cn"
        chapter={5}
        page={105}
        onSelectBlock={() => undefined}
      />,
    );

    await waitFor(() => expect(renderPage).toHaveBeenCalledTimes(1));
    notifyResize();
    expect(renderPage).toHaveBeenCalledTimes(1);

    finishFirst();
    await waitFor(() => expect(renderPage).toHaveBeenCalledTimes(2));
  });

  it("reuses the PDF document and cancels the old page render on navigation", async () => {
    let finishFirst: () => void = () => undefined;
    const firstRender = new Promise<void>((resolve) => {
      finishFirst = resolve;
    });
    const cancelFirst = vi.fn();
    getPage
      .mockResolvedValueOnce({
        getViewport: ({ scale }: { scale: number }) => ({
          width: 595 * scale,
          height: 842 * scale,
        }),
        render: () => ({ promise: firstRender, cancel: cancelFirst }),
      })
      .mockResolvedValue({
        getViewport: ({ scale }: { scale: number }) => ({
          width: 595 * scale,
          height: 842 * scale,
        }),
        render: () => ({ promise: Promise.resolve(), cancel: vi.fn() }),
      });

    const view = render(
      <PdfReader
        bookId="rtr4-cn"
        chapter={5}
        page={105}
        onSelectBlock={() => undefined}
      />,
    );
    await waitFor(() => expect(getPage).toHaveBeenCalledWith(105));

    view.rerender(
      <PdfReader
        bookId="rtr4-cn"
        chapter={5}
        page={106}
        onSelectBlock={() => undefined}
      />,
    );

    await waitFor(() => expect(getPage).toHaveBeenCalledWith(106));
    expect(getDocument).toHaveBeenCalledTimes(1);
    expect(cancelFirst).toHaveBeenCalledOnce();
    finishFirst();
  });

  it("shows errors raised by a resize render", async () => {
    let notifyResize: () => void = () => undefined;
    vi.stubGlobal(
      "ResizeObserver",
      class {
        constructor(callback: ResizeObserverCallback) {
          notifyResize = () => callback([], this as unknown as ResizeObserver);
        }
        observe() {}
        disconnect() {}
        unobserve() {}
      },
    );
    const renderPage = vi
      .fn()
      .mockReturnValueOnce({ promise: Promise.resolve(), cancel: vi.fn() })
      .mockImplementationOnce(() => ({
        promise: Promise.reject(new Error("resize failed")),
        cancel: vi.fn(),
      }));
    getPage.mockResolvedValue({
      getViewport: ({ scale }: { scale: number }) => ({
        width: 595 * scale,
        height: 842 * scale,
      }),
      render: renderPage,
    });

    render(
      <PdfReader
        bookId="rtr4-cn"
        chapter={5}
        page={105}
        onSelectBlock={() => undefined}
      />,
    );
    await waitFor(() => expect(renderPage).toHaveBeenCalledOnce());
    notifyResize();

    expect(await screen.findByRole("alert")).toHaveTextContent(
      "PDF 页面加载失败：resize failed",
    );
  });
});
