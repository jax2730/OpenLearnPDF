import type { SourceBlock } from "../types";

interface BlockOverlayProps {
  blocks: SourceBlock[];
  selectedBlockId?: string;
  onSelectBlock: (blockId: string) => void;
}

function percent(value: number): string {
  return `${Math.round(value * 1000000) / 10000}%`;
}

function blockLabel(block: SourceBlock): string {
  const kind = block.type === "formula" ? "公式" : "来源块";
  const identity = block.number ?? block.id;
  return `${kind} ${identity}，第 ${block.page} 页`;
}

export function BlockOverlay({
  blocks,
  selectedBlockId,
  onSelectBlock,
}: BlockOverlayProps) {
  return (
    <div
      aria-label="页面来源块"
      style={{ position: "absolute", inset: 0, pointerEvents: "none" }}
    >
      {blocks.map((block) => {
        const selected = block.id === selectedBlockId;
        return (
          <button
            aria-label={blockLabel(block)}
            aria-pressed={selected}
            key={block.id}
            onClick={() => onSelectBlock(block.id)}
            style={{
              position: "absolute",
              left: percent(block.bbox.x0),
              top: percent(block.bbox.y0),
              width: percent(block.bbox.x1 - block.bbox.x0),
              height: percent(block.bbox.y1 - block.bbox.y0),
              pointerEvents: "auto",
              border: selected ? "3px solid #ff8a00" : "2px solid #2b7fff",
              background: selected
                ? "rgba(255, 138, 0, 0.22)"
                : "rgba(43, 127, 255, 0.12)",
              cursor: "pointer",
            }}
          />
        );
      })}
    </div>
  );
}
