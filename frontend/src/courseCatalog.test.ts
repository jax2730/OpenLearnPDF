import { expect, it } from "vitest";
import { courseForPage, type CourseEntry } from "./courseCatalog";
it("associates only cited pages, preserves selected overlap and accepts another chapter", () => {
  const courses: CourseEntry[] = [
    { id: "a", chapter_slug: "chapter-05", section_slug: "section-5.1", section: "5.1", title: "A", start_page: 105, source_pages: [105, 106] },
    { id: "b", chapter_slug: "chapter-20", section_slug: "section-20.1", section: "20.1", title: "B", start_page: 708, source_pages: [708, 710] },
  ];
  expect(courseForPage(courses, 106, "section-5.1")?.id).toBe("a");
  expect(courseForPage(courses, 709)).toBeUndefined();
  expect(courseForPage(courses, 710)?.chapter_slug).toBe("chapter-20");
});
