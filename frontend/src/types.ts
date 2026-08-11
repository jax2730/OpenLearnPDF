export type BlockType =
  | "text"
  | "heading"
  | "formula"
  | "figure"
  | "figure_caption"
  | "table"
  | "code"
  | "list"
  | "page_header"
  | "page_footer";

export interface BoundingBox {
  x0: number;
  y0: number;
  x1: number;
  y1: number;
}

export interface SourceRelation {
  type: string;
  target: string;
}

export interface SourceBlock {
  id: string;
  type: BlockType;
  page: number;
  bbox: BoundingBox;
  text?: string | null;
  latex?: string | null;
  number?: string | null;
  asset_path?: string | null;
  relations: SourceRelation[];
}

export interface PageDocument {
  page: number;
  blocks: SourceBlock[];
  width_points?: number | null;
  height_points?: number | null;
}

export interface LessonSection {
  level: string;
  title: string;
  body: string;
  citations: string[];
}

export interface Lesson {
  id: string;
  chapter: number;
  section: string;
  title: string;
  sections: LessonSection[];
}

export interface ShaderExample {
  id: string;
  language: "glsl";
  stage: "fragment";
  expected_visual: string;
  external_references: string[];
}

export interface LessonBundle {
  lesson: Lesson;
  shader: ShaderExample;
  shader_source: string;
  browser_shader_source: string;
}
