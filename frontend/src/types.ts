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
