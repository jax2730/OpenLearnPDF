import { useEffect, useRef, useState } from "react";
import { GlobalWorkerOptions, getDocument } from "pdfjs-dist";
import type { PDFDocumentProxy, RenderTask } from "pdfjs-dist";
import workerUrl from "pdfjs-dist/build/pdf.worker.min.mjs?url";

import { getPage as fetchPage } from "../api";
import type { PageDocument } from "../types";
import { BlockOverlay } from "./BlockOverlay";

GlobalWorkerOptions.workerSrc = workerUrl;

interface PdfReaderProps {
  bookId: string;
  chapter: number;
  page: number;
  selectedBlockId?: string;
  onSelectBlock: (blockId: string) => void;
}

export function PdfReader({
  bookId,
  chapter,
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

  useEffect(() => {
    const controller = new AbortController();
    setPageData(undefined);
    setDataError(undefined);
    fetchPage(bookId, chapter, page, controller.signal)
      .then(setPageData)
      .catch((reason: unknown) => {
        if (!controller.signal.aborted) {
          setDataError(reason instanceof Error ? reason.message : "页面数据不可用");
        }
      });
    return () => controller.abort();
  }, [bookId, chapter, page]);

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
              const targetWidth = frame.clientWidth || base.width;
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
    };
  }, [pdfDocument, page]);

  const error = dataError ?? pdfError;

  return (
    <section aria-label={`PDF 第 ${page} 页`}>
      {error ? <p role="alert">PDF 页面加载失败：{error}</p> : null}
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
        {pageData ? (
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
