import type { SourceBlock } from "../types";

interface SourceCitationProps {
  block: SourceBlock;
  onNavigate: (page: number, blockId: string) => void;
}

function sourceName(block: SourceBlock) {
  if (block.type === "formula") return `公式 ${block.number ?? block.id}`;
  return block.number ? `${block.type} ${block.number}` : block.id;
}

export function SourceCitation({ block, onNavigate }: SourceCitationProps) {
  const name = sourceName(block);
  return (
    <button
      aria-label={`查看来源：第 ${block.page} 页，${name}`}
      onClick={() => onNavigate(block.page, block.id)}
      type="button"
    >
      第 {block.page} 页 · {name}
    </button>
  );
}
