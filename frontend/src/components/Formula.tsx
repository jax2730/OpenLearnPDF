import { useEffect, useRef, useState } from "react";
import katex from "katex";
import "katex/dist/katex.min.css";

interface FormulaProps {
  latex: string;
  label: string;
  displayMode?: boolean;
}

export function Formula({ latex, label, displayMode = true }: FormulaProps) {
  const hostRef = useRef<HTMLDivElement>(null);
  const [error, setError] = useState<string>();

  useEffect(() => {
    const host = hostRef.current;
    if (!host) return;
    host.textContent = "";
    setError(undefined);
    try {
      katex.render(latex, host, {
        displayMode,
        strict: "error",
        throwOnError: true,
        trust: false,
      });
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "无效公式");
    }
  }, [displayMode, latex]);

  return (
    <div aria-label={label}>
      <div ref={hostRef} />
      {error ? <p role="alert">公式渲染失败：{error}</p> : null}
    </div>
  );
}
