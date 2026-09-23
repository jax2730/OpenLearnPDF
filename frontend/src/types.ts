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

export type LearningCardKind =
  | "intuition"
  | "derivation"
  | "visual"
  | "numeric_example"
  | "code"
  | "pitfall"
  | "exercise";

export interface LearningCard {
  id: string;
  kind: LearningCardKind;
  title: string;
  body: string;
  citations: string[];
}

export interface KnowledgePoint {
  id: string;
  title: string;
  summary: string;
  primary_source_id: string;
  citations: string[];
  cards: LearningCard[];
}

export interface Lesson {
  id: string;
  chapter: number;
  section: string;
  title: string;
  sections: LessonSection[];
  knowledge_points?: KnowledgePoint[];
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

export interface RetrievalCitation {
  block_id: string;
  page: number;
  bbox: BoundingBox;
  block_type: BlockType;
  source_excerpt: string;
  latex?: string | null;
  score: number;
}

export interface QuestionAnswer {
  status: "answered" | "insufficient_evidence";
  mode: "local_extractive" | "configured_provider";
  answer: string;
  citations: RetrievalCitation[];
}
