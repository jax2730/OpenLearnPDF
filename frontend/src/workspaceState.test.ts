import { expect, it } from "vitest";
import { readWorkspace, saveWorkspace, boundStudyRatio } from "./workspaceState";

it("validates saved preferences without persisting compact state", () => {
  localStorage.setItem("openlearn:workspace:v1", '{"sidebarOpen":false,"studyRatio":0.42,"compactPanel":"study"}');
  expect(readWorkspace()).toEqual({ sidebarOpen: false, studyRatio: 0.42 });
  for (const value of ["broken", "null", '{"studyRatio":"0.5"}', '{"studyRatio":9}']) {
    localStorage.setItem("openlearn:workspace:v1", value);
    expect(readWorkspace().studyRatio).toBe(0.4);
  }
  saveWorkspace({ sidebarOpen: true, studyRatio: 0.4 });
  expect(localStorage.getItem("openlearn:workspace:v1")).not.toContain("compactPanel");
});

it("respects minimum source and study widths", () => {
  expect(boundStudyRatio(0, 960)).toBeCloseTo(320 / 948);
  expect(boundStudyRatio(1, 960)).toBeCloseTo(1 - 480 / 948);
  expect(boundStudyRatio(NaN, 1200)).toBe(0.4);
});
