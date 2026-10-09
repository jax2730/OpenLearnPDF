export interface CourseEntry {
  id: string; chapter_slug: string; section_slug: string; section: string; title: string;
  start_page: number; source_pages: number[];
}
export function courseForPage(courses: CourseEntry[], page: number, current?: string) {
  const matches = courses.filter((course) => course.source_pages.includes(page));
  return matches.find((course) => course.section_slug === current) ?? matches.sort((a, b) => b.section.length - a.section.length)[0];
}
