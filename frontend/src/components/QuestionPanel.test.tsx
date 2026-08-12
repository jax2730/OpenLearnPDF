import { fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { QuestionPanel } from "./QuestionPanel";

const citation = {
  block_id: "p105-formula-5.1",
  page: 105,
  bbox: { x0: 0.1, y0: 0.5, x1: 0.9, y1: 0.6 },
  block_type: "formula",
  source_excerpt: "Gooch 使用冷暖色表达表面方向。",
  latex: "c_{shaded}",
  score: 0.9,
  score_components: { lexical: 0.9, embedding: 0, type_bonus: 0 },
};

afterEach(() => vi.unstubAllGlobals());

describe("QuestionPanel", () => {
  it("shows a local grounded answer and navigable citations", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({
        ok: true,
        json: async () => ({
          status: "answered",
          mode: "local_extractive",
          answer: "Gooch 使用冷暖色插值。",
          citations: [citation],
        }),
      }),
    );
    const onNavigateSource = vi.fn();
    render(<QuestionPanel onNavigateSource={onNavigateSource} />);

    fireEvent.change(screen.getByLabelText("问题"), {
      target: { value: "Gooch 如何表达方向？" },
    });
    fireEvent.click(screen.getByRole("button", { name: "提问" }));

    expect(await screen.findByText("Gooch 使用冷暖色插值。")).toBeInTheDocument();
    expect(screen.getByText("状态：已回答")).toBeInTheDocument();
    expect(screen.getByText("本地降级模式")).toBeInTheDocument();
    const source = screen.getByRole("button", {
      name: "查看回答来源：第 105 页，p105-formula-5.1",
    });
    fireEvent.click(source);
    expect(onNavigateSource).toHaveBeenCalledWith(105, "p105-formula-5.1");
    expect(fetch).toHaveBeenCalledWith(
      "/api/questions",
      expect.objectContaining({ method: "POST" }),
    );
  });

  it("shows an insufficient-evidence message", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({
        ok: true,
        json: async () => ({
          status: "insufficient_evidence",
          mode: "local_extractive",
          answer: "",
          citations: [],
        }),
      }),
    );
    render(<QuestionPanel onNavigateSource={() => undefined} />);

    fireEvent.change(screen.getByLabelText("问题"), {
      target: { value: "没有证据的问题" },
    });
    fireEvent.click(screen.getByRole("button", { name: "提问" }));

    expect(
      await screen.findByText("现有来源不足，无法可靠回答。"),
    ).toBeInTheDocument();
    expect(screen.getByText("状态：证据不足")).toBeInTheDocument();
  });
});
