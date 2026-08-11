import { useEffect, useState } from "react";

import { getBlock, getLesson } from "../api";
import type { LessonBundle, SourceBlock } from "../types";
import { Formula } from "./Formula";
import { SourceCitation } from "./SourceCitation";

interface LessonPanelProps {
  chapterSlug: string;
  sectionSlug: string;
  onNavigateSource: (page: number, blockId: string) => void;
}

function isHttps(url: string) {
  try {
    return new URL(url).protocol === "https:";
  } catch {
    return false;
  }
}

export function LessonPanel({
  chapterSlug,
  sectionSlug,
  onNavigateSource,
}: LessonPanelProps) {
  const [bundle, setBundle] = useState<LessonBundle>();
  const [blocks, setBlocks] = useState<Map<string, SourceBlock>>(new Map());
  const [error, setError] = useState<string>();

  useEffect(() => {
    const controller = new AbortController();
    setBundle(undefined);
    setBlocks(new Map());
    setError(undefined);

    getLesson(chapterSlug, sectionSlug, controller.signal)
      .then(async (lessonBundle) => {
        const citationIds = [
          ...new Set(
            lessonBundle.lesson.sections.flatMap((section) => section.citations),
          ),
        ];
        const citedBlocks = await Promise.all(
          citationIds.map((id) => getBlock(id, controller.signal)),
        );
        if (!controller.signal.aborted) {
          setBundle(lessonBundle);
          setBlocks(new Map(citedBlocks.map((block) => [block.id, block])));
        }
      })
      .catch((reason: unknown) => {
        if (!controller.signal.aborted) {
          setError(reason instanceof Error ? reason.message : "课程不可用");
        }
      });

    return () => controller.abort();
  }, [chapterSlug, sectionSlug]);

  if (error) return <p role="alert">课程加载失败：{error}</p>;
  if (!bundle) return <p>正在加载课程…</p>;

  return (
    <article aria-label={`课程 ${bundle.lesson.section}`}>
      <h2>{bundle.lesson.title}</h2>
      {bundle.lesson.sections.map((section) => (
        <section key={section.level}>
          <h3>{section.title}</h3>
          <p>{section.body}</p>
          {section.citations.map((id) => {
            const block = blocks.get(id);
            if (!block) return null;
            return (
              <div key={id}>
                {block.latex ? (
                  <Formula
                    latex={block.latex}
                    label={`公式 ${block.number ?? block.id}`}
                  />
                ) : null}
                <SourceCitation block={block} onNavigate={onNavigateSource} />
              </div>
            );
          })}
        </section>
      ))}

      <section>
        <h3>Shader 示例</h3>
        <p>{bundle.shader.expected_visual}</p>
        <pre>
          <code>{bundle.shader_source}</code>
        </pre>
        <details>
          <summary>ShaderToy 版本</summary>
          <pre>
            <code>{bundle.browser_shader_source}</code>
          </pre>
        </details>
        {bundle.shader.external_references.filter(isHttps).map((url) => (
          <a
            href={url}
            key={url}
            rel="noopener noreferrer"
            target="_blank"
          >
            打开 ShaderToy 演示
          </a>
        ))}
      </section>
    </article>
  );
}
