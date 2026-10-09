import { fireEvent, render, screen } from "@testing-library/react";
import { expect, it, vi } from "vitest";
import { RenderingGuide } from "./RenderingGuide";

it("links exact PDF pages and keeps independent explanations expandable", () => {
  const navigate = vi.fn();
  render(<RenderingGuide onNavigateSource={navigate} />);
  expect(screen.getByRole("heading", { name: "前向、延迟与后处理：从一帧的产生开始" })).toBeInTheDocument();
  fireEvent.click(screen.getByRole("button", { name: "20.1 延迟着色 · PDF 708" }));
  expect(navigate).toHaveBeenCalledWith(708);
  const examples = screen.getAllByText("代码与实践");
  expect(examples.length).toBeGreaterThan(1);
  fireEvent.click(examples[0]); fireEvent.click(examples[1]);
  expect(examples[0].closest("details")).toHaveAttribute("open");
  expect(examples[1].closest("details")).toHaveAttribute("open");
  expect(screen.getByText(/不是延迟渲染/)).toBeInTheDocument();
});
