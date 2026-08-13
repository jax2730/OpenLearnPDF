import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { Formula } from "./Formula";
import { LessonPanel } from "./LessonPanel";

const lessonBundle = {
  lesson: {
    id: "chapter-05-section-5.1",
    chapter: 5,
    section: "5.1",
    title: "Gooch 着色",
    sections: [
      {
        level: "mathematics",
        title: "数学结构",
        body: "先计算基础色，再混合高光。",
        citations: ["p105-formula-5.1"],
      },
    ],
    questions: [],
    shader_example_id: "gooch",
    shader_metadata_path: "examples/gooch.json",
  },
  shader: {
    id: "gooch",
    language: "glsl",
    stage: "fragment",
    source_path: "examples/gooch.frag",
    browser_source_path: "examples/gooch-shadertoy.frag",
    source_block_ids: ["p105-formula-5.1"],
    expected_visual: "冷蓝到暖黄的球体，并带窄白色高光。",
    verification_command: "glslangValidator -S frag gooch.frag",
    external_references: ["https://www.shadertoy.com/new"],
  },
  shader_source: "#version 330 core\nvoid main() {}",
  browser_shader_source: "void mainImage(out vec4 c, in vec2 p) {}",
};

const formulaBlock = {
  id: "p105-formula-5.1",
  type: "formula",
  page: 105,
  bbox: { x0: 0.1, y0: 0.5, x1: 0.9, y1: 0.6 },
  latex: "c_{shaded}=s c_{highlight}+(1-s)c_{cool}",
  number: "5.1",
  relations: [],
  source: { parser: "mineru", version: "2", confidence: 0.99 },
};

const knowledgeBundle = {
  ...lessonBundle,
  lesson: {
    ...lessonBundle.lesson,
    id: "chapter-05-section-5.2.2",
    section: "5.2.2",
    knowledge_points: [
      {
        id: "vector",
        title: "光向量",
        summary: "方向与距离。",
        primary_source_id: "p105-formula-5.1",
        citations: ["p105-formula-5.1"],
        cards: [
          {
            id: "idea",
            kind: "intuition",
            title: "向量",
            body: "连接两点。",
            citations: ["p105-formula-5.1"],
          },
        ],
      },
      {
        id: "falloff",
        title: "距离衰减",
        summary: "平方反比。",
        primary_source_id: "p111-formula-5.11",
        citations: ["p111-formula-5.11"],
        cards: [
          {
            id: "numbers",
            kind: "numeric_example",
            title: "数值",
            body: "距离翻倍。",
            citations: ["p111-formula-5.11"],
          },
        ],
      },
    ],
  },
};

const falloffBlock = {
  ...formulaBlock,
  id: "p111-formula-5.11",
  page: 111,
  number: "5.11",
  latex: "c(r)=c_0/r^2",
};

describe("LessonPanel", () => {
  beforeEach(() => {
    vi.stubGlobal(
      "fetch",
      vi.fn((url: string) => {
        const payload = url.startsWith("/api/lessons/")
          ? lessonBundle
          : formulaBlock;
        return Promise.resolve({ ok: true, json: async () => payload });
      }),
    );
  });

  afterEach(() => vi.unstubAllGlobals());

  it("renders formula 5.1 and navigates through its citation", async () => {
    const onNavigateSource = vi.fn();
    const { container } = render(
      <LessonPanel
        chapterSlug="chapter-05"
        sectionSlug="section-5.1"
        onNavigateSource={onNavigateSource}
      />,
    );

    await waitFor(() => expect(container.querySelector(".katex")).not.toBeNull());
    const citation = screen.getByRole("button", {
      name: "查看来源：第 105 页，公式 5.1",
    });
    fireEvent.click(citation);
    expect(onNavigateSource).toHaveBeenCalledWith(105, "p105-formula-5.1");
  });

  it("shows shader code, expected result and a safe external demo link", async () => {
    render(
      <LessonPanel
        chapterSlug="chapter-05"
        sectionSlug="section-5.1"
        onNavigateSource={() => undefined}
      />,
    );

    expect(await screen.findByText(/#version 330 core/)).toBeInTheDocument();
    expect(screen.getByText(/冷蓝到暖黄/)).toBeInTheDocument();
    const demo = screen.getByRole("link", { name: "打开 ShaderToy 演示" });
    expect(demo).toHaveAttribute("target", "_blank");
    expect(demo).toHaveAttribute("rel", "noopener noreferrer");
    expect(demo).toHaveAttribute("href", "https://www.shadertoy.com/new");
  });

  it("shows a KaTeX error instead of injecting invalid markup", async () => {
    render(<Formula latex="\\notARealCommand{" label="错误公式" />);

    expect(await screen.findByRole("alert")).toHaveTextContent("公式渲染失败");
  });

  it("selects the knowledge point that cites the selected PDF block", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn((url: string) => {
        const payload = url.startsWith("/api/lessons/")
          ? knowledgeBundle
          : url.includes("p111-formula-5.11")
            ? falloffBlock
            : formulaBlock;
        return Promise.resolve({ ok: true, json: async () => payload });
      }),
    );
    const view = render(
      <LessonPanel
        chapterSlug="chapter-05"
        sectionSlug="section-5.2.2"
        selectedBlockId="p105-formula-5.1"
        onNavigateSource={() => undefined}
      />,
    );

    expect(await screen.findByText("连接两点。")).toBeInTheDocument();
    view.rerender(
      <LessonPanel
        chapterSlug="chapter-05"
        sectionSlug="section-5.2.2"
        selectedBlockId="p111-formula-5.11"
        onNavigateSource={() => undefined}
      />,
    );
    expect(await screen.findByText("距离翻倍。")).toBeInTheDocument();
  });
});
