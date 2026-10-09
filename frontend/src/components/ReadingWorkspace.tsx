import { type ReactNode, useEffect, useRef, useState } from "react";
import { boundStudyRatio, readWorkspace, saveWorkspace } from "../workspaceState";

export function ReadingWorkspace({ source, study, sourceRequest = 0 }: { source: ReactNode; study: ReactNode; sourceRequest?: number }) {
  const [preference, setPreference] = useState(readWorkspace);
  const [width, setWidth] = useState(1200);
  const [panel, setPanel] = useState<"pdf" | "study">("pdf");
  const root = useRef<HTMLDivElement>(null);
  const toggle = useRef<HTMLButtonElement>(null);
  const frame = useRef<number | null>(null);
  const desiredRatio = useRef(preference.studyRatio);
  const compact = width < 960;
  const ratio = boundStudyRatio(preference.studyRatio, width);

  useEffect(() => {
    const element = root.current;
    if (!element || typeof ResizeObserver === "undefined") return;
    const observer = new ResizeObserver(([entry]) => { if (entry?.contentRect.width > 0) setWidth(entry.contentRect.width); });
    observer.observe(element);
    return () => { observer.disconnect(); if (frame.current !== null) cancelAnimationFrame(frame.current); };
  }, []);
  useEffect(() => { saveWorkspace(preference); }, [preference]);
  useEffect(() => { if (sourceRequest > 0) { setPanel("pdf"); requestAnimationFrame(() => root.current?.querySelector<HTMLButtonElement>(".page-controls button")?.focus()); } }, [sourceRequest]);

  const updateRatio = (next: number) => setPreference((current) => ({ ...current, studyRatio: boundStudyRatio(next, width) }));
  const finishDrag = () => {
    if (frame.current !== null) { cancelAnimationFrame(frame.current); frame.current = null; updateRatio(desiredRatio.current); }
  };

  return <div ref={root} className="reading-workspace-shell">
    <div className="workspace-actions">
      {compact ? <nav aria-label="阅读面板">
        <button type="button" aria-pressed={panel === "pdf"} onClick={() => setPanel("pdf")}>原书</button>
        <button type="button" aria-pressed={panel === "study"} onClick={() => setPanel("study")}>伴读</button>
      </nav> : <button ref={toggle} type="button" aria-expanded={preference.sidebarOpen} aria-controls="companion-pane" onClick={() => {
        setPreference((current) => ({ ...current, sidebarOpen: !current.sidebarOpen })); toggle.current?.focus();
      }}>{preference.sidebarOpen ? "收起伴读" : "展开伴读"}</button>}
      <span>{compact ? "原书与伴读分别保留位置" : preference.sidebarOpen ? "拖动中线调整比例 · 聚焦中线可用方向键" : "专注原书 · 翻页不会自动展开伴读"}</span>
    </div>
    <div className={`learning-workspace${compact ? " is-compact" : preference.sidebarOpen ? "" : " is-focused"}`}
      style={{ gridTemplateColumns: !compact && preference.sidebarOpen ? `minmax(0, ${1 - ratio}fr) 12px minmax(0, ${ratio}fr)` : "minmax(0, 1fr)" }}>
      <div className="source-slot" hidden={compact && panel !== "pdf"}>{source}</div>
      {!compact && preference.sidebarOpen ? <div className="workspace-separator" role="separator" tabIndex={0} aria-label="调整原书与伴读宽度" aria-orientation="vertical"
        aria-valuemin={Math.ceil(boundStudyRatio(0, width) * 100)} aria-valuemax={Math.floor(boundStudyRatio(1, width) * 100)} aria-valuenow={Math.round(ratio * 100)}
        onKeyDown={(event) => {
          if (!["ArrowLeft", "ArrowRight", "Home"].includes(event.key)) return;
          event.preventDefault(); updateRatio(event.key === "Home" ? 0.4 : ratio + (event.key === "ArrowLeft" ? 0.02 : -0.02));
        }}
        onPointerDown={(event) => { if (event.button === 0) event.currentTarget.setPointerCapture(event.pointerId); }}
        onPointerMove={(event) => {
          if (!event.currentTarget.hasPointerCapture(event.pointerId) || !root.current) return;
          const rect = root.current.getBoundingClientRect();
          desiredRatio.current = 1 - (event.clientX - rect.left) / rect.width;
          if (frame.current === null) frame.current = requestAnimationFrame(() => { frame.current = null; updateRatio(desiredRatio.current); });
        }} onPointerUp={finishDrag} onPointerCancel={finishDrag} /> : null}
      <div id="companion-pane" className="study-slot" hidden={compact ? panel !== "study" : !preference.sidebarOpen}>{study}</div>
    </div>
  </div>;
}
