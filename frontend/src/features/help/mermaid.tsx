import { useEffect, useId, useMemo, useState } from 'react'

type MermaidRenderState =
  | { status: 'loading' }
  | { status: 'ready'; svg: string }
  | { status: 'error'; message: string }

type ResolvedTheme = 'dark'
type MermaidApi = typeof import('mermaid').default

let mermaidRenderIndex = 0
let mermaidLoadPromise: Promise<MermaidApi> | null = null
let mermaidConfiguredTheme: ResolvedTheme | null = null

const mermaidSvgCache = new Map<string, string>()
const mermaidFontFamily =
  '"Inter Variable", ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", "PingFang SC", "Hiragino Sans GB", "Microsoft YaHei UI", "Microsoft YaHei", "Noto Sans CJK SC", "Source Han Sans SC", "Noto Sans SC", sans-serif'

export function MermaidDiagram({ chart }: { chart: string }) {
  const reactId = useId()
  const diagramId = useMemo(() => `omedia-mermaid-${reactId.replace(/[^a-zA-Z0-9_-]/g, '')}`, [reactId])
  const resolvedTheme: ResolvedTheme = 'dark'
  const [state, setState] = useState<MermaidRenderState>({ status: 'loading' })

  useEffect(() => {
    let cancelled = false

    async function renderDiagram() {
      setState({ status: 'loading' })

      try {
        const cacheKey = `${resolvedTheme}:${chart}`
        const cachedSvg = mermaidSvgCache.get(cacheKey)

        if (cachedSvg) {
          if (!cancelled) setState({ status: 'ready', svg: cachedSvg })
          return
        }

        const mermaid = await loadMermaid()
        configureMermaid(mermaid, resolvedTheme)
        const renderId = `${diagramId}-${resolvedTheme}-${mermaidRenderIndex++}`

        const { svg } = await mermaid.render(renderId, chart)
        mermaidSvgCache.set(cacheKey, svg)
        if (!cancelled) setState({ status: 'ready', svg })
      } catch (error) {
        if (!cancelled) setState({ status: 'error', message: errorMessage(error) })
      }
    }

    void renderDiagram()

    return () => {
      cancelled = true
    }
  }, [chart, diagramId, resolvedTheme])

  if (state.status === 'loading') {
    return (
      <div className="flex min-h-40 items-center justify-center rounded-md border bg-muted/20 px-4 py-8 text-sm text-muted-foreground">
        Rendering diagram...
      </div>
    )
  }

  if (state.status === 'error') {
    return (
      <div className="rounded-md border border-destructive/50 bg-destructive/10 p-4">
        <p className="text-sm font-medium text-foreground">Diagram could not be rendered.</p>
        <p className="mt-1 text-xs text-muted-foreground">{state.message}</p>
        <pre className="mt-3 overflow-x-auto rounded-md bg-background/70 p-3 text-xs text-foreground">
          <code>{chart}</code>
        </pre>
      </div>
    )
  }

  return (
    <figure
      aria-label="Rendered Mermaid diagram"
      className="overflow-x-auto rounded-md border bg-card p-4 text-foreground"
      dangerouslySetInnerHTML={{ __html: state.svg }}
      role="img"
    />
  )
}

function loadMermaid() {
  mermaidLoadPromise ??= import('mermaid').then((module) => module.default)
  return mermaidLoadPromise
}

function configureMermaid(mermaid: MermaidApi, resolvedTheme: ResolvedTheme) {
  if (mermaidConfiguredTheme === resolvedTheme) return

  mermaid.initialize({
    startOnLoad: false,
    securityLevel: 'strict',
    theme: 'base',
    fontFamily: mermaidFontFamily,
    flowchart: {
      curve: 'basis',
      htmlLabels: true,
      padding: 18,
    },
    themeVariables: {
      background: 'transparent',
      primaryColor: '#2a2e42',
      primaryTextColor: '#e7e3fc',
      primaryBorderColor: '#6e66ed',
      secondaryColor: '#103c4e',
      secondaryTextColor: '#e7e3fc',
      secondaryBorderColor: '#16b1ff',
      tertiaryColor: '#1c1f2e',
      tertiaryTextColor: '#e7e3fc',
      tertiaryBorderColor: '#9155fd',
      lineColor: '#8a8d93',
      edgeLabelBackground: '#14161f',
      clusterBkg: '#14161f',
      clusterBorder: '#4a5072',
      fontFamily: mermaidFontFamily,
    },
  })
  mermaidConfiguredTheme = resolvedTheme
}

function errorMessage(error: unknown) {
  return error instanceof Error ? error.message : String(error)
}
