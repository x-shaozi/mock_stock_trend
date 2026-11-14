import { createRouter, createWebHistory, type RouteRecordRaw } from 'vue-router'
import PhasePlaceholderView from '../views/PhasePlaceholderView.vue'

const routes: RouteRecordRaw[] = [
  { path: '/', redirect: '/stocks' },
  {
    path: '/stocks',
    component: PhasePlaceholderView,
    props: {
      title: '我的股票',
      description: 'S1 将接入 GET /stocks，支持分页、市场与关键词筛选。',
    },
  },
  {
    path: '/stocks/add',
    component: PhasePlaceholderView,
    props: { title: '添加股票', description: 'S1 将接入外部股票搜索及股票登记接口。' },
  },
  {
    path: '/stocks/archived',
    component: PhasePlaceholderView,
    props: { title: '已归档股票', description: 'S1 将支持查看与恢复已归档股票。' },
  },
  {
    path: '/stocks/:stockId',
    component: PhasePlaceholderView,
    props: { title: '股票详情', description: 'S2 将接入 GET /stocks/{stock_id} 与历史日线查询。' },
  },
  {
    path: '/stocks/:stockId/analysis/:runId',
    component: PhasePlaceholderView,
    props: { title: '历史分析快照', description: 'S3 将展示某一 run_id 对应的逐日分析结果。' },
  },
  {
    path: '/:pathMatch(.*)*',
    component: PhasePlaceholderView,
    props: { title: '页面不存在', description: '请返回我的股票页面。' },
  },
]

export default createRouter({ history: createWebHistory(), routes })
