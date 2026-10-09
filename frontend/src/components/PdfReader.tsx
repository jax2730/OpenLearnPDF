import { useEffect, useRef, useState } from "react";
import { GlobalWorkerOptions, getDocument } from "pdfjs-dist";
import type { PDFDocumentProxy, RenderTask } from "pdfjs-dist";
import workerUrl from "pdfjs-dist/build/pdf.worker.min.mjs?url";

import { getBookPage as fetchPage } from "../api";
import type { PageDocument } from "../types";
import { BlockOverlay } from "./BlockOverlay";
import { restoreAnchor } from "../readingAnchor";

GlobalWorkerOptions.workerSrc = workerUrl;

interface PdfReaderProps {
  bookId: string;
  chapter?: number;
  page: number;
  selectedBlockId?: string;
  onSelectBlock: (blockId: string) => void;
}

export function PdfReader({
  bookId,
  page,
  selectedBlockId,
  onSelectBlock,
}: PdfReaderProps) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const frameRef = useRef<HTMLDivElement>(null);
  const [pageData, setPageData] = useState<PageDocument>();
  const [pdfDocument, setPdfDocument] = useState<PDFDocumentProxy>();
  const [aspectRatio, setAspectRatio] = useState<number>();
  const [dataError, setDataError] = useState<string>();
  const [pdfError, setPdfError] = useState<string>();
  const [showBlocks, setShowBlocks] = useState(true);

  useEffect(() => {
    const controller = new AbortController();
    setPageData(undefined);
    setDataError(undefined);
    fetchPage(bookId, page, controller.signal)
      .then((data) => { if (!controller.signal.aborted) setPageData(data); })
      .catch((reason: unknown) => {
        if (!controller.signal.aborted) {
          setDataError(reason instanceof Error ? reason.message : "页面数据不可用");
        }
      });
    return () => controller.abort();
  }, [bookId, page]);

  useEffect(() => {
    let disposed = false;
    const loadingTask = getDocument({
      url: `/api/books/${encodeURIComponent(bookId)}/source`,
    });
    setPdfDocument(undefined);
    setPdfError(undefined);

    loadingTask.promise
      .then((document) => {
        if (!disposed) setPdfDocument(document);
      })
      .catch((reason: unknown) => {
        if (!disposed) {
          setPdfError(reason instanceof Error ? reason.message : "PDF 文档不可用");
        }
      });

    return () => {
      disposed = true;
      void loadingTask.destroy();
    };
  }, [bookId]);

  useEffect(() => {
    if (!pdfDocument) return;
    let disposed = false;
    let resizeObserver: ResizeObserver | undefined;
    let activeRenderTask: RenderTask | undefined;
    const pane = frameRef.current?.closest<HTMLElement>(".source-pane");
    let anchor = -1;
    let interaction = 0;
    let renderedHeight = 0;
    let renderedTop = 0;
    if (pane) pane.scrollTop = 0;
    const remember = () => {
      if (!pane || !renderedHeight || !frameRef.current?.clientWidth) return;
      anchor = pane.scrollTop === 0 ? -1 : Math.max(0, Math.min(1, (pane.scrollTop + (pane.querySelector<HTMLElement>(".source-toolbar")?.offsetHeight ?? 0) - renderedTop) / renderedHeight));
    };
    const userInput = () => { interaction++; };
    pane?.addEventListener("scroll", remember);
    for (const event of ["wheel", "touchstart", "pointerdown", "keydown"]) pane?.addEventListener(event, userInput, { passive: true });
    setPdfError(undefined);

    const handleRenderError = (reason: unknown) => {
      if (disposed || (reason instanceof Error && reason.name === "RenderingCancelledException")) {
        return;
      }
      setPdfError(reason instanceof Error ? reason.message : "PDF 页面不可用");
    };

    pdfDocument
      .getPage(page)
      .then((pdfPage) => {
        if (disposed) return;
        let rendering = false;
        let rerenderRequested = false;
        const render = async () => {
          if (rendering) {
            rerenderRequested = true;
            return;
          }
          rendering = true;
          try {
            do {
              rerenderRequested = false;
              const canvas = canvasRef.current;
              const frame = frameRef.current;
              if (disposed || !canvas || !frame) return;
              const base = pdfPage.getViewport({ scale: 1 });
              const targetWidth = frame.clientWidth;
              if (targetWidth <= 0) return;
              const token = interaction;
              const savedAnchor = anchor;
              const viewport = pdfPage.getViewport({
                scale: targetWidth / base.width,
              });
              const context = canvas.getContext("2d");
              if (!context) throw new Error("浏览器不支持 Canvas 2D");
              canvas.width = Math.ceil(viewport.width);
              canvas.height = Math.ceil(viewport.height);
              setAspectRatio(viewport.width / viewport.height);
              activeRenderTask = pdfPage.render({
                canvas,
                canvasContext: context,
                viewport,
              });
              await activeRenderTask.promise;
              activeRenderTask = undefined;
              if (disposed) return;
              renderedHeight = viewport.height;
              if (pane) {
                renderedTop = canvas.getBoundingClientRect().top - pane.getBoundingClientRect().top + pane.scrollTop;
                if (interaction === token && savedAnchor !== null) pane.scrollTop = restoreAnchor(savedAnchor, renderedTop, renderedHeight, pane.querySelector<HTMLElement>(".source-toolbar")?.offsetHeight ?? 0, pane.scrollHeight - pane.clientHeight);
                remember();
              }
            } while (rerenderRequested && !disposed);
          } finally {
            rendering = false;
          }
        };

        const scheduleRender = () => void render().catch(handleRenderError);
        scheduleRender();
        if (typeof ResizeObserver !== "undefined") {
          resizeObserver = new ResizeObserver(scheduleRender);
          if (frameRef.current) resizeObserver.observe(frameRef.current);
        }
      })
      .catch(handleRenderError);

    return () => {
      disposed = true;
      resizeObserver?.disconnect();
      activeRenderTask?.cancel();
      pane?.removeEventListener("scroll", remember);
      for (const event of ["wheel", "touchstart", "pointerdown", "keydown"]) pane?.removeEventListener(event, userInput);
    };
  }, [pdfDocument, page]);

  return (
    <section aria-label={`PDF 第 ${page} 页`}>
      <label className="overlay-toggle"><input type="checkbox" checked={showBlocks} onChange={(event) => setShowBlocks(event.target.checked)} /> 显示来源定位框（关闭可专注阅读）</label>
      {pdfError ? <p role="alert">PDF 页面加载失败：{pdfError}</p> : null}
      {dataError ? <p role="status">页面解析数据不可用，原书仍可阅读：{dataError}</p> : null}
      {pageData?.analysis_status === "not_parsed" ? <p role="status">本页尚未解析，可继续阅读原书；暂无区域定位。</p> : null}
      <div
        ref={frameRef}
        style={{
          position: "relative",
          width: "100%",
          maxWidth: 900,
          aspectRatio,
        }}
      >
        <canvas
          key={`${bookId}-${page}`}
          ref={canvasRef}
          style={{ display: "block", width: "100%" }}
        />
        {pageData && showBlocks ? (
          <BlockOverlay
            blocks={pageData.blocks}
            selectedBlockId={selectedBlockId}
            onSelectBlock={onSelectBlock}
          />
        ) : null}
      </div>
    </section>
  );
}
