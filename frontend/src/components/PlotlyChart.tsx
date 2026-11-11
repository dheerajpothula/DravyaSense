import { useEffect, useRef } from 'react'
import Plotly from 'plotly.js-dist-min'

/**
 * Thin React wrapper around Plotly.js.
 *
 * Uses `Plotly.react` which both creates and updates the plot efficiently.
 * The plot is purged on unmount to free DOM and memory resources.
 *
 * data / layout / config should be memoised by the parent to avoid
 * unnecessary re-renders.
 */

export interface PlotlyChartProps {
  data:     any[]
  layout:   any
  config?:  any
  style?:   React.CSSProperties
  className?: string
}

export default function PlotlyChart({
  data, layout, config, style, className,
}: PlotlyChartProps) {
  const ref = useRef<HTMLDivElement>(null)

  useEffect(() => {
    const el = ref.current
    if (!el) return

    Plotly.react(
      el,
      data,
      layout,
      config ?? { displayModeBar: false, responsive: true },
    )

    return () => { Plotly.purge(el) }
  }, [data, layout, config])

  return <div ref={ref} className={className} style={style} />
}
