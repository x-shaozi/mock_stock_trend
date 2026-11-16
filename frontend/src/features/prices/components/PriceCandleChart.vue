<script setup lang="ts">
import { onBeforeUnmount, onMounted, ref, watch } from 'vue'
import * as echarts from 'echarts/core'
import { BarChart, CandlestickChart } from 'echarts/charts'
import {
  AxisPointerComponent,
  DataZoomComponent,
  GridComponent,
  TooltipComponent,
} from 'echarts/components'
import { CanvasRenderer } from 'echarts/renderers'
import type { EChartsType } from 'echarts/core'
import { useTheme } from '../../../composables/useTheme'
import type { Market } from '../../stocks/types'
import type { CandleChartData } from '../utils/chart-data'

echarts.use([
  CandlestickChart,
  BarChart,
  GridComponent,
  TooltipComponent,
  AxisPointerComponent,
  DataZoomComponent,
  CanvasRenderer,
])

const props = defineProps<{ data: CandleChartData; market: Market }>()
const element = ref<InstanceType<typeof globalThis.HTMLDivElement> | null>(null)
const { appliedTheme } = useTheme()
let instance: EChartsType | undefined
let observer: InstanceType<typeof globalThis.ResizeObserver> | undefined

function renderChart(): void {
  if (!element.value) return
  if (!instance) instance = echarts.init(element.value, undefined, { renderer: 'canvas' })
  const dark = appliedTheme.value === 'dark'
  const ink = dark ? '#b3c0d2' : '#66758b'
  const grid = dark ? '#334051' : '#e7ecf3'
  // A 股：红涨绿跌；美股：绿涨红跌。严格根据市场设置。
  const rising = props.market === 'CN' ? '#e05a60' : '#1aa887'
  const falling = props.market === 'CN' ? '#19a184' : '#e05a60'
  const firstVisible = Math.max(0, 100 - (65 / Math.max(65, props.data.dates.length)) * 100)
  instance.setOption(
    {
      animation: false,
      backgroundColor: 'transparent',
      grid: [
        { left: 66, right: 24, top: 27, height: '56%' },
        { left: 66, right: 24, top: '71%', height: '16%' },
      ],
      tooltip: { trigger: 'axis', axisPointer: { type: 'cross' } },
      axisPointer: {
        link: [{ xAxisIndex: 'all' }],
        label: { backgroundColor: dark ? '#445369' : '#6e7f98' },
      },
      xAxis: [
        {
          type: 'category',
          data: props.data.dates,
          gridIndex: 0,
          boundaryGap: true,
          axisLabel: { show: false },
          axisLine: { lineStyle: { color: grid } },
          axisTick: { show: false },
        },
        {
          type: 'category',
          data: props.data.dates,
          gridIndex: 1,
          boundaryGap: true,
          axisLabel: { color: ink, fontSize: 11 },
          axisLine: { lineStyle: { color: grid } },
          axisTick: { show: false },
        },
      ],
      yAxis: [
        {
          type: 'value',
          scale: true,
          gridIndex: 0,
          axisLabel: { color: ink },
          splitLine: { lineStyle: { color: grid } },
        },
        {
          type: 'value',
          scale: true,
          gridIndex: 1,
          axisLabel: {
            color: ink,
            formatter: (value: number | string) => {
              const n = Number(value)
              return n >= 1e6
                ? `${(n / 1e6).toFixed(1)}M`
                : n >= 1000
                  ? `${(n / 1000).toFixed(0)}K`
                  : String(value)
            },
          },
          splitLine: { show: false },
        },
      ],
      dataZoom: [
        { type: 'inside', xAxisIndex: [0, 1], start: firstVisible, end: 100 },
        {
          type: 'slider',
          xAxisIndex: [0, 1],
          start: firstVisible,
          end: 100,
          bottom: 4,
          height: 18,
          textStyle: { color: ink },
          borderColor: grid,
        },
      ],
      series: [
        {
          name: '日 K',
          type: 'candlestick',
          xAxisIndex: 0,
          yAxisIndex: 0,
          data: props.data.candles,
          itemStyle: { color: rising, color0: falling, borderColor: rising, borderColor0: falling },
        },
        {
          name: '成交量',
          type: 'bar',
          xAxisIndex: 1,
          yAxisIndex: 1,
          data: props.data.volumes.map((value, index) => ({
            value,
            itemStyle: {
              color:
                props.data.candles[index]![1] >= props.data.candles[index]![0] ? rising : falling,
            },
          })),
        },
      ],
    },
    { notMerge: true },
  )
}

onMounted(() => {
  renderChart()
  if (element.value) {
    observer = new globalThis.ResizeObserver(() => instance?.resize())
    observer.observe(element.value)
  }
})
watch([() => props.data, () => props.market, appliedTheme], renderChart)
onBeforeUnmount(() => {
  observer?.disconnect()
  instance?.dispose()
  instance = undefined
})
</script>

<template>
  <div
    ref="element"
    class="candlestick-chart"
    role="img"
    aria-label="日 K 线及成交量图表，支持缩放查看交易日"
  />
</template>
