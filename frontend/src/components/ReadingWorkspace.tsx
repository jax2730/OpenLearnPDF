import { type ReactNode, useLayoutEffect, useRef, useState } from "react";
import { restoreAnchor } from "../readingAnchor";

const preferenceKey = "openlearn:workspace:v1";
function readPreference() {
  try {
    const value = JSON.parse(localStorage.getItem(preferenceKey) ?? "null");
    return typeof value?.sidebarOpen === "boolean" ? value.sidebarOpen : true;
  } catch { return true; }
}

export function ReadingWorkspace({ source, study }: { source: ReactNode; study: ReactNode }) {
  const [open, setOpen] = useState(readPreference);
  const root = useRef<HTMLDivElement>(null);
  const toggle = useRef<HTMLButtonElement>(null);
  const pendingAnchor = useRef<number | null>(null);

  const changeOpen = () => {
    const pane = root.current?.querySelector<HTMLElement>(".source-pane");
    const canvas = pane?.querySelector("canvas");
    const header = pane?.querySelector<HTMLElement>(".source-toolbar");
    if (pane && canvas && canvas.clientHeight > 0) {
      const top = canvas.getBoundingClientRect().top - pane.getBoundingClientRect().top + pane.scrollTop;
      pendingAnchor.current = pane.scrollTop === 0 ? -1 : Math.max(0, Math.min(1, (pane.scrollTop + (header?.offsetHeight ?? 0) - top) / canvas.clientHeight));
    }
    setOpen(!open);
    try { localStorage.setItem(preferenceKey, JSON.stringify({ sidebarOpen: !open })); } catch { /* Reading remains usable without storage. */ }
    toggle.current?.focus();
  };

  useLayoutEffect(() => {
    const ratio = pendingAnchor.current;
    pendingAnchor.current = null;
    if (ratio === null) return;
    const pane = root.current?.querySelector<HTMLElement>(".source-pane");
    const canvas = pane?.querySelector("canvas");
    const header = pane?.querySelector<HTMLElement>(".source-toolbar");
    if (!pane || !canvas) return;
    const top = canvas.getBoundingClientRect().top - pane.getBoundingClientRect().top + pane.scrollTop;
    pane.scrollTop = restoreAnchor(ratio, top, canvas.clientHeight, header?.offsetHeight ?? 0, pane.scrollHeight - pane.clientHeight);
  }, [open]);

  return <div ref={root} className="reading-workspace-shell">
    <div className="workspace-actions">
      <button ref={toggle} type="button" aria-expanded={open} aria-controls="companion-pane" onClick={changeOpen}>{open ? "收起伴读" : "展开伴读"}</button>
      <span>{open ? "原书与讲解对照阅读" : "专注原书 · 翻页不会自动展开伴读"}</span>
    </div>
    <div className={`learning-workspace${open ? "" : " is-focused"}`}>
      <div className="source-slot">{source}</div>
      <div id="companion-pane" className="study-slot" hidden={!open}>{study}</div>
    </div>
  </div>;
}
