import guide from "../../../content/rtr4-cn/guides/rendering-paths.json";

export function RenderingGuide({ onNavigateSource }: { onNavigateSource: (page: number) => void }) {
  return <article className="rendering-guide" aria-label="跨章渲染流程入门">
    <h2>{guide.title}</h2>
    <p className="study-guide">{guide.scope}</p>
    <nav aria-label="入门知识点"><ol>{guide.sections.map((section) => <li key={section.id}><a href={`#guide-${section.id}`}>{section.title}</a></li>)}</ol></nav>
    {guide.sections.map((section) => <section key={section.id} id={`guide-${section.id}`}>
      <h3>{section.title}</h3>
      {section.body.map((paragraph) => <p key={paragraph}>{paragraph}</p>)}
      {section.flow ? <pre className="render-flow">{section.flow}</pre> : null}
      <div className="source-links">{section.sources.map((source) => <button key={`${source.page}-${source.label}`} type="button" onClick={() => onNavigateSource(source.page)}>{source.label} · PDF {source.page}</button>)}</div>
      {section.details.map((detail) => <details key={detail.title}><summary>{detail.title}</summary>
        {detail.body.map((paragraph) => <p key={paragraph}>{paragraph}</p>)}
        {"code" in detail ? <pre><code>{detail.code}</code></pre> : null}
      </details>)}
    </section>)}
    <p>实践入口：<a href="https://www.shadertoy.com/new" target="_blank" rel="noopener noreferrer">ShaderToy 编辑器</a>（外链不会自动载入示例；无需安装本地 Shader 运行器）。</p>
  </article>;
}
