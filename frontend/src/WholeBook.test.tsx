import { fireEvent, render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import App from "./App";
import { getBook } from "./api";

vi.mock("./api", () => ({ getBook: vi.fn(), getCourses: vi.fn().mockResolvedValue({ courses: [] }) }));
vi.mock("./components/PdfReader", () => ({ PdfReader: ({ page }: { page: number }) => <div aria-label="PDF 阅读器">{page}</div> }));
vi.mock("./components/QuestionPanel", () => ({ QuestionPanel: () => <div>来源检索</div> }));
vi.mock("./components/LessonPanel", () => ({ LessonPanel: () => <div>当前课程</div> }));
const book = { id: "rtr4-cn", title: "RTR4", page_count: 903, chapters: [
  { id: "5", title: "基础着色", start_page: 104, end_page: 154 },
  { id: "6", title: "纹理", start_page: 155, end_page: 180 },
] };
function jump(page: string) {
  fireEvent.change(screen.getByLabelText("PDF 页码"), { target: { value: page } });
  fireEvent.click(screen.getByRole("button", { name: "跳转" }));
}
describe("whole-book reader", () => {
  beforeEach(() => { localStorage.clear(); vi.mocked(getBook).mockReset().mockResolvedValue(book); });
  it("does not reopen the companion after page navigation", async () => {
    render(<App />);
    await screen.findByText(/全书共 903 页/);
    fireEvent.click(screen.getByRole("button", { name: "收起伴读" }));
    jump("903");
    expect(screen.getByRole("button", { name: "展开伴读" })).toHaveAttribute("aria-expanded", "false");
    expect(screen.queryByRole("region", { name: "知识点学习区" })).not.toBeInTheDocument();
  });
  it("uses book bounds and hides unrelated lessons", async () => {
    render(<App />);
    await screen.findByText(/全书共 903 页/);
    jump("904");
    expect(screen.getByRole("alert")).toHaveTextContent("1–903");
    jump("903");
    expect(screen.getByLabelText("PDF 阅读器")).toHaveTextContent("903");
    expect(screen.getByRole("button", { name: "下一页" })).toBeDisabled();
    jump("1");
    expect(screen.getByRole("button", { name: "上一页" })).toBeDisabled();
    expect(screen.queryByText("当前课程")).not.toBeInTheDocument();
    expect(screen.getByText(/本页暂无已发布精讲/)).toBeInTheDocument();
  });
  it("navigates registered chapters without inventing teaching coverage", async () => {
    render(<App />);
    await screen.findByText(/全书共 903 页/);
    fireEvent.click(screen.getByRole("button", { name: /纹理/ }));
    expect(screen.getByLabelText("PDF 阅读器")).toHaveTextContent("155");
    expect(screen.queryByText("当前课程")).not.toBeInTheDocument();
    expect(screen.getByText(/目录仅显示已登记章节/)).toBeInTheDocument();
  });
  it("offers retry when book metadata fails", async () => {
    vi.mocked(getBook).mockRejectedValueOnce(new Error("offline"));
    render(<App />);
    expect(await screen.findByRole("alert")).toHaveTextContent("offline");
    fireEvent.click(screen.getByRole("button", { name: "重试" }));
    expect(await screen.findByText(/全书共 903 页/)).toBeInTheDocument();
  });
});
