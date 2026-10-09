import { useMemo, useState } from "react";

import type { KnowledgePoint, SourceBlock } from "../types";
import { Formula } from "./Formula";
import { SourceCitation } from "./SourceCitation";

interface KnowledgeLessonPanelProps {
  lessonId: string;
  points: KnowledgePoint[];
  blocks: Map<string, SourceBlock>;
  activePointId: string;
  onSelectPoint: (pointId: string, page: number, blockId: string) => void;
  onNavigateSource: (page: number, blockId: string) => void;
}

function progressKey(lessonId: string) {
  return `rtr4-progress:${lessonId}`;
}

function loadCompleted(lessonId: string): Set<string> {
  try {
    const value = JSON.parse(localStorage.getItem(progressKey(lessonId)) ?? "[]");
    return new Set(Array.isArray(value) ? value.filter((id) => typeof id === "string") : []);
  } catch {
    return new Set();
  }
}

export function KnowledgeLessonPanel({
  lessonId,
  points,
  blocks,
  activePointId,
  onSelectPoint,
  onNavigateSource,
}: KnowledgeLessonPanelProps) {
  const activePoint =
    points.find((point) => point.id === activePointId) ?? points[0];
  const [expanded, setExpanded] = useState<Record<string, boolean>>({});
  const [completed, setCompleted] = useState(() => loadCompleted(lessonId));

  const validCompleted = useMemo(
    () => new Set([...completed].filter((id) => points.some((point) => point.id === id))),
    [completed, points],
  );

  if (!activePoint) return <p role="alert">知识点不可用</p>;

  const selectPoint = (point: KnowledgePoint) => {
    const block = blocks.get(point.primary_source_id);
    if (block) onSelectPoint(point.id, block.page, block.id);
  };

  const markCompleted = () => {
    const next = new Set(validCompleted).add(activePoint.id);
    setCompleted(next);
    try {
      localStorage.setItem(progressKey(lessonId), JSON.stringify([...next]));
    } catch {
      // Reading must remain available when storage is blocked.
    }
  };

  return (
    <section aria-label="知识点学习">
      <header>
        <p>已掌握 {validCompleted.size} / {points.length}</p>
        <nav aria-label="知识点目录">
          {points.map((point, index) => (
            <button
              aria-current={point.id === activePoint.id ? "step" : undefined}
              key={point.id}
              onClick={() => selectPoint(point)}
              type="button"
            >
              {index + 1}. {point.title}
            </button>
          ))}
        </nav>
      </header>

      <article>
        <p>{activePoint.summary}</p>
        {activePoint.cards.map((card, index) => {
          const identity = `${activePoint.id}:${card.id}`;
          const content = <>
            <p>{card.body}</p>
            {card.citations.map((id) => {
          const block = blocks.get(id);
          if (!block) return <p key={id}>来源暂不可用：{id}</p>;
          return (
            <div key={id}>
              {block.latex ? (
                <Formula latex={block.latex} label={`公式 ${block.number ?? block.id}`} />
              ) : null}
              <SourceCitation block={block} onNavigate={onNavigateSource} />
            </div>
          );
            })}
          </>;
          return card.kind === "intuition" || (index === 0 && !activePoint.cards.some((item) => item.kind === "intuition")) ? <section key={identity}><h3>{card.title}</h3>{content}</section> : <details key={identity} open={expanded[identity] ?? false} onToggle={(event) => {
            const next = event.currentTarget.open;
            setExpanded((current) => current[identity] === next ? current : { ...current, [identity]: next });
          }}><summary>{card.title}</summary>{content}</details>;
        })}
        <div>
          <button onClick={markCompleted} type="button">标记已掌握</button>
        </div>
      </article>
    </section>
  );
}
