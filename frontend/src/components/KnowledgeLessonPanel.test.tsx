import { fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import type { KnowledgePoint, SourceBlock } from "../types";
import { KnowledgeLessonPanel } from "./KnowledgeLessonPanel";

const points: KnowledgePoint[] = [
  {
    id: "vector",
    title: "光向量",
    summary: "从位置得到方向和距离。",
    primary_source_id: "p109-formula-5.9",
    citations: ["p109-formula-5.9"],
    cards: [
      {
        id: "idea",
        kind: "intuition",
        title: "直觉",
        body: "先连接两个点。",
        citations: ["p109-formula-5.9"],
      },
      {
        id: "steps",
        kind: "derivation",
        title: "推导",
        body: "计算 d、r、l。",
        citations: ["p110-formula-5.10"],
      },
    ],
  },
  {
    id: "falloff",
    title: "平方反比",
    summary: "距离翻倍，强度四分之一。",
    primary_source_id: "p111-formula-5.11",
    citations: ["p111-formula-5.11"],
    cards: [
      {
        id: "numbers",
        kind: "numeric_example",
        title: "数字例子",
        body: "r=2 时为 1/4。",
        citations: ["p111-formula-5.11"],
      },
    ],
  },
];

const blocks = new Map<string, SourceBlock>([
  [
    "p109-formula-5.9",
    {
      id: "p109-formula-5.9",
      type: "formula",
      page: 109,
      bbox: { x0: 0.1, y0: 0.2, x1: 0.9, y1: 0.3 },
      latex: "l=d/r",
      number: "5.9",
      relations: [],
    },
  ],
  [
    "p110-formula-5.10",
    {
      id: "p110-formula-5.10",
      type: "formula",
      page: 110,
      bbox: { x0: 0.1, y0: 0.2, x1: 0.9, y1: 0.3 },
      latex: "d=p_l-p",
      number: "5.10",
      relations: [],
    },
  ],
  [
    "p111-formula-5.11",
    {
      id: "p111-formula-5.11",
      type: "formula",
      page: 111,
      bbox: { x0: 0.1, y0: 0.2, x1: 0.9, y1: 0.3 },
      latex: "c(r)=c_0(r_0/r)^2",
      number: "5.11",
      relations: [],
    },
  ],
]);

describe("KnowledgeLessonPanel", () => {
  afterEach(() => localStorage.clear());

  it("selects a point and navigates to its primary source", () => {
    const onSelectPoint = vi.fn();
    render(
      <KnowledgeLessonPanel
        lessonId="lesson"
        points={points}
        blocks={blocks}
        activePointId="vector"
        onSelectPoint={onSelectPoint}
        onNavigateSource={() => undefined}
      />,
    );

    fireEvent.click(screen.getByRole("button", { name: /平方反比/ }));
    expect(onSelectPoint).toHaveBeenCalledWith(
      "falloff",
      111,
      "p111-formula-5.11",
    );
  });

  it("shows one card at a time and moves to the next card", () => {
    render(
      <KnowledgeLessonPanel
        lessonId="lesson"
        points={points}
        blocks={blocks}
        activePointId="vector"
        onSelectPoint={() => undefined}
        onNavigateSource={() => undefined}
      />,
    );

    expect(screen.getByRole("heading", { name: "直觉" })).toBeInTheDocument();
    expect(screen.queryByRole("heading", { name: "推导" })).toBeNull();
    fireEvent.click(screen.getByRole("button", { name: "下一步" }));
    expect(screen.getByRole("heading", { name: "推导" })).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "上一步" }));
    expect(screen.getByRole("heading", { name: "直觉" })).toBeInTheDocument();
  });

  it("navigates citations and stores completed points", () => {
    const onNavigateSource = vi.fn();
    render(
      <KnowledgeLessonPanel
        lessonId="lesson"
        points={points}
        blocks={blocks}
        activePointId="vector"
        onSelectPoint={() => undefined}
        onNavigateSource={onNavigateSource}
      />,
    );

    fireEvent.click(
      screen.getByRole("button", { name: "查看来源：第 109 页，公式 5.9" }),
    );
    expect(onNavigateSource).toHaveBeenCalledWith(109, "p109-formula-5.9");
    fireEvent.click(screen.getByRole("button", { name: "标记已掌握" }));
    expect(localStorage.getItem("rtr4-progress:lesson")).toContain("vector");
    expect(screen.getByText("已掌握 1 / 2")).toBeInTheDocument();
  });
});
