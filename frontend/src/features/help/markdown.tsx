import { Children, isValidElement, memo, type ComponentProps, type ReactNode } from 'react'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import { MermaidDiagram } from './mermaid'
import { headingText, slugifyHeading } from './sections'

type CodeElementProps = ComponentProps<'code'> & {
  className?: string
  children?: ReactNode
}

const remarkPlugins = [remarkGfm]
const markdownComponents = createMarkdownComponents()

export const GuideArticle = memo(function GuideArticle({ guide }: { guide: string }) {
  return (
    <article className="mx-auto flex w-full max-w-4xl flex-col gap-4 text-sm leading-7 text-foreground">
      <ReactMarkdown components={markdownComponents} remarkPlugins={remarkPlugins}>
        {guide}
      </ReactMarkdown>
    </article>
  )
})

function createMarkdownComponents() {
  return {
    h1({ children }: ComponentProps<'h1'>) {
      return <h1 className="scroll-mt-8 text-3xl font-bold leading-tight">{children}</h1>
    },
    h2({ children }: ComponentProps<'h2'>) {
      const text = headingText(children)

      return (
        <h2 id={slugifyHeading(text)} className="mt-7 scroll-mt-28 border-t pt-6 text-xl font-semibold leading-snug">
          {children}
        </h2>
      )
    },
    h3({ children }: ComponentProps<'h3'>) {
      return <h3 className="mt-4 text-base font-semibold leading-snug">{children}</h3>
    },
    p({ children }: ComponentProps<'p'>) {
      return <p className="text-muted-foreground">{children}</p>
    },
    ul({ children }: ComponentProps<'ul'>) {
      return <ul className="flex list-disc flex-col gap-1 pl-6 text-muted-foreground">{children}</ul>
    },
    ol({ children }: ComponentProps<'ol'>) {
      return <ol className="flex list-decimal flex-col gap-1 pl-6 text-muted-foreground">{children}</ol>
    },
    li({ children }: ComponentProps<'li'>) {
      return <li>{children}</li>
    },
    strong({ children }: ComponentProps<'strong'>) {
      return <strong className="font-semibold text-foreground">{children}</strong>
    },
    pre({ children }: ComponentProps<'pre'>) {
      const child = Children.toArray(children)[0]

      if (isValidElement<CodeElementProps>(child) && child.props.className?.includes('language-mermaid')) {
        return <MermaidDiagram chart={String(child.props.children ?? '').trim()} />
      }

      return <pre className="overflow-x-auto rounded-md border bg-muted/35 p-4 text-xs leading-relaxed text-foreground">{children}</pre>
    },
    code({ children, className }: CodeElementProps) {
      if (className) {
        return <code className={`${className} whitespace-pre font-mono text-xs`}>{children}</code>
      }

      return <code className="rounded bg-muted px-1.5 py-0.5 text-xs text-foreground">{children}</code>
    },
    table({ children }: ComponentProps<'table'>) {
      return (
        <div className="overflow-x-auto rounded-md border bg-card">
          <table className="w-full min-w-[760px] border-collapse text-left text-sm">{children}</table>
        </div>
      )
    },
    thead({ children }: ComponentProps<'thead'>) {
      return <thead className="bg-muted/45 text-foreground">{children}</thead>
    },
    tbody({ children }: ComponentProps<'tbody'>) {
      return <tbody className="divide-y">{children}</tbody>
    },
    tr({ children }: ComponentProps<'tr'>) {
      return <tr className="align-top">{children}</tr>
    },
    th({ children }: ComponentProps<'th'>) {
      return <th className="whitespace-nowrap border-r px-3 py-2 text-sm font-semibold last:border-r-0">{children}</th>
    },
    td({ children }: ComponentProps<'td'>) {
      return <td className="border-r px-3 py-2 text-muted-foreground last:border-r-0">{children}</td>
    },
  }
}
