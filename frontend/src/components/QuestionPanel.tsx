import { type FormEvent, useEffect, useRef, useState } from "react";

import { askQuestion } from "../api";
import type { QuestionAnswer } from "../types";

interface QuestionPanelProps {
  onNavigateSource: (page: number, blockId: string) => void;
}

export function QuestionPanel({ onNavigateSource }: QuestionPanelProps) {
  const [question, setQuestion] = useState("");
  const [result, setResult] = useState<QuestionAnswer>();
  const [error, setError] = useState<string>();
  const [pending, setPending] = useState(false);
  const requestRef = useRef<AbortController | undefined>(undefined);

  useEffect(() => () => requestRef.current?.abort(), []);

  const submit = (event: FormEvent) => {
    event.preventDefault();
    const normalized = question.trim();
    if (!normalized) return;
    requestRef.current?.abort();
    const controller = new AbortController();
    requestRef.current = controller;
    setPending(true);
    setError(undefined);
    setResult(undefined);
    askQuestion(normalized, controller.signal)
      .then((answer) => {
        if (!controller.signal.aborted) setResult(answer);
      })
      .catch((reason: unknown) => {
        if (!controller.signal.aborted) {
          setError(reason instanceof Error ? reason.message : "回答不可用");
        }
      })
      .finally(() => {
        if (!controller.signal.aborted) setPending(false);
      });
  };

  return (
    <section aria-label="来源问答">
      <h2>基于本书提问</h2>
      <form onSubmit={submit}>
        <label>
          问题
          <textarea
            aria-label="问题"
            maxLength={512}
            onChange={(event) => setQuestion(event.target.value)}
            value={question}
          />
        </label>
        <button disabled={pending || !question.trim()} type="submit">
          {pending ? "检索中…" : "提问"}
        </button>
      </form>
      {error ? <p role="alert">问答失败：{error}</p> : null}
      {result ? (
        <p>
          状态：{result.status === "answered" ? "已回答" : "证据不足"}
        </p>
      ) : null}
      {result?.mode === "local_extractive" ? <p>本地降级模式</p> : null}
      {result?.status === "insufficient_evidence" ? (
        <p>现有来源不足，无法可靠回答。</p>
      ) : null}
      {result?.status === "answered" ? (
        <div aria-live="polite">
          <p>{result.answer}</p>
          {result.citations.map((source) => (
            <button
              aria-label={`查看回答来源：第 ${source.page} 页，${source.block_id}`}
              key={source.block_id}
              onClick={() => onNavigateSource(source.page, source.block_id)}
              type="button"
            >
              第 {source.page} 页 · {source.block_id}
            </button>
          ))}
        </div>
      ) : null}
    </section>
  );
}
