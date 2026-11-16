<script setup lang="ts">
import { onBeforeUnmount, onMounted, ref, watch } from 'vue'
import * as echarts from 'echarts/core'
import { BarChart, LineChart } from 'echarts/charts'
import {
  AxisPointerComponent,
  DataZoomComponent,
  GridComponent,
  TooltipComponent,
} from 'echarts/components'
import { CanvasRenderer } from 'echarts/renderers'
import type { EChartsType } from 'echarts/core'
import { useTheme } from '../../../composables/useTheme'
import type { AnalysisChartData } from '../utils/analysis-chart-data'

// 只注册三联图需要的 ECharts 模块，不把完整图表库塞进入口包。
echarts.use([
  BarChart,
  LineChart,
  GridComponent,
  DataZoomComponent,
  TooltipComponent,
  AxisPointerComponent,
  CanvasRenderer,
])

const props = defineProps<{ data: AnalysisChartData }>()
const target = ref<InstanceType<typeof globalThis.HTMLDivElement> | null>(null)
const { appliedTheme } = useTheme()
let chart: EChartsType | undefined
let observer: InstanceType<typeof globalThis.ResizeObserver> | undefined

function renderChart(): void {
  if (!target.value) return
  chart ??= echarts.init(target.value, undefined, { renderer: 'canvas' })
  const dark = appliedTheme.value === 'dark'
  const labelColor = dark ? '#bac7d9' : '#66758b'
  const axisColor = dark ? '#334051' : '#e1e6ee'
  const zoomStart =
    props.data.dates.length <= 65
      ? 0
      : (100 * (props.data.dates.length - 65)) / props.data.dates.length

  // 三个 grid 各有一条相同日期的 x 轴；一个 dataZoom 同时控制三个 x 轴。
  chart.setOption(
    {
      animation: false,
      backgroundColor: 'transparent',
      color: ['#5b8ff9', '#f0ae40', '#a487d8', '#39a99c'],
      grid: [
        { left: 64, right: 25, top: 30, height: '43%' },
        { left: 64, right: 25, top: '54%', height: '15%' },
        { left: 64, right: 25, top: '74%', height: '15%' },
      ],
      tooltip: { trigger: 'axis', axisPointer: { type: 'cross' } },
      axisPointer: { link: [{ xAxisIndex: 'all' }] },
      xAxis: [0, 1, 2].map((index) => ({
        type: 'category',
        gridIndex: index,
        data: props.data.dates,
        boundaryGap: true,
        axisLabel: { color: labelColor, show: index === 2, fontSize: 11 },
        axisLine: { lineStyle: { color: axisColor } },
        axisTick: { show: false },
      })),
      yAxis: [
        {
          type: 'value',
          gridIndex: 0,
          scale: true,
          axisLabel: { color: labelColor },
          splitLine: { lineStyle: { color: axisColor } },
        },
        {
          type: 'value',
          gridIndex: 1,
          min: 0,
          max: 100,
          axisLabel: { color: labelColor },
          splitLine: { lineStyle: { color: axisColor } },
        },
        {
          type: 'value',
          gridIndex: 2,
          scale: true,
          axisLabel: { color: labelColor },
          splitLine: { lineStyle: { color: axisColor } },
        },
      ],
      dataZoom: [
        { type: 'inside', xAxisIndex: [0, 1, 2], start: zoomStart, end: 100 },
        {
          type: 'slider',
          xAxisIndex: [0, 1, 2],
          start: zoomStart,
          end: 100,
          bottom: 2,
          height: 16,
          textStyle: { color: labelColor },
        },
      ],
      series: [
        {
          name: '收盘价',
          type: 'line',
          xAxisIndex: 0,
          yAxisIndex: 0,
          symbol: 'none',
          data: props.data.close,
        },
        {
          name: 'MA5',
          type: 'line',
          xAxisIndex: 0,
          yAxisIndex: 0,
          symbol: 'none',
          connectNulls: false,
          data: props.data.ma5,
        },
        {
          name: 'MA20',
          type: 'line',
          xAxisIndex: 0,
          yAxisIndex: 0,
          symbol: 'none',
          connectNulls: false,
          data: props.data.ma20,
        },
        {
          name: 'RSI14',
          type: 'line',
          xAxisIndex: 1,
          yAxisIndex: 1,
          symbol: 'none',
          connectNulls: false,
          data: props.data.rsi14,
        },
        {
          name: 'MACD 柱值 (DIF-DEA)',
          type: 'bar',
          xAxisIndex: 2,
          yAxisIndex: 2,
          // 后端在预热阶段返回 null；ECharts 对 null 不绘柱。
          data: props.data.macd.map((value) =>
            value === null
              ? null
              : { value, itemStyle: { color: value >= 0 ? '#1aa887' : '#e05a60' } },
          ),
        },
      ],
    },
    { notMerge: true },
  )
}

onMounted(() => {
  renderChart()
  if (target.value) {
    observer = new globalThis.ResizeObserver(() => chart?.resize())
    observer.observe(target.value)
  }
})
watch([() => props.data, appliedTheme], renderChart)
onBeforeUnmount(() => {
  observer?.disconnect()
  chart?.dispose()
  chart = undefined
})
</script>

<template>
  <div
    ref="target"
    class="analysis-indicators-chart"
    role="img"
    aria-label="分析快照收盘价与 MA5 MA20、RSI14 和 MACD 柱值三个联动图表"
  />
</template>
