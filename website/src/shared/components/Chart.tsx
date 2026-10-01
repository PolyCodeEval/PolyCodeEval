import { useEffect, useRef } from 'react'
import * as echarts from 'echarts/core'
import type { EChartsCoreOption as EChartsOption } from 'echarts/core'
import { BarChart, BoxplotChart, HeatmapChart } from 'echarts/charts'
import {
  GridComponent,
  LegendComponent,
  TooltipComponent,
  VisualMapComponent,
} from 'echarts/components'
import { CanvasRenderer, SVGRenderer } from 'echarts/renderers'
import { Download } from 'lucide-react'

echarts.use([
  BarChart,
  BoxplotChart,
  HeatmapChart,
  GridComponent,
  LegendComponent,
  TooltipComponent,
  VisualMapComponent,
  CanvasRenderer,
  SVGRenderer,
])

export function Chart({
  option,
  height = 330,
  name = 'chart',
}: {
  option: EChartsOption
  height?: number
  name?: string
}) {
  const ref = useRef<HTMLDivElement>(null)
  const chart = useRef<echarts.ECharts | null>(null)
  useEffect(() => {
    if (!ref.current) return
    chart.current = echarts.init(ref.current, undefined, { renderer: 'canvas' })
    chart.current.setOption(option)
    const resize = () => chart.current?.resize()
    const observer = new ResizeObserver(resize)
    observer.observe(ref.current)
    return () => {
      observer.disconnect()
      chart.current?.dispose()
      chart.current = null
    }
  }, [])
  useEffect(() => {
    chart.current?.setOption(option, true)
  }, [option])
  const download = (type: 'png' | 'svg') => {
    let temporary: HTMLDivElement | null = null
    let exportChart: echarts.ECharts | null = null
    if (type === 'svg' && ref.current) {
      temporary = document.createElement('div')
      temporary.style.cssText = `position:fixed;left:-10000px;top:0;width:${ref.current.clientWidth}px;height:${ref.current.clientHeight}px`
      document.body.appendChild(temporary)
      exportChart = echarts.init(temporary, undefined, { renderer: 'svg' })
      exportChart.setOption(option)
    }
    const url = (exportChart ?? chart.current)?.getDataURL({
      type,
      pixelRatio: 2,
      backgroundColor: '#fff',
    })
    exportChart?.dispose()
    temporary?.remove()
    if (!url) return
    const a = document.createElement('a')
    a.href = url
    a.download = `${name}.${type}`
    a.click()
  }
  return (
    <div className="chart-wrap">
      <details className="chart-download">
        <summary className="icon-button" aria-label={`Download ${name}`} title="Download chart">
          <Download size={16} />
        </summary>
        <div className="chart-download-menu">
          <button onClick={() => download('png')}>PNG</button>
          <button onClick={() => download('svg')}>SVG</button>
        </div>
      </details>
      <div ref={ref} style={{ height }} role="img" aria-label={`${name} visualization`} />
    </div>
  )
}
