export interface WorkspacePreference { sidebarOpen: boolean; studyRatio: number }
const key = "openlearn:workspace:v1";
export function readWorkspace(): WorkspacePreference {
  try {
    const value = JSON.parse(localStorage.getItem(key) ?? "null");
    return {
      sidebarOpen: typeof value?.sidebarOpen === "boolean" ? value.sidebarOpen : true,
      studyRatio: typeof value?.studyRatio === "number" && Number.isFinite(value.studyRatio) && value.studyRatio >= 0.2 && value.studyRatio <= 0.6 ? value.studyRatio : 0.4,
    };
  } catch { return { sidebarOpen: true, studyRatio: 0.4 }; }
}
export function saveWorkspace(value: WorkspacePreference) {
  try { localStorage.setItem(key, JSON.stringify(value)); } catch { /* Optional preference. */ }
}
export function boundStudyRatio(ratio: number, width: number) {
  const available = Math.max(800, width - 12);
  return Math.max(0.2, 320 / available, Math.min(0.6, 1 - 480 / available, Number.isFinite(ratio) ? ratio : 0.4));
}
