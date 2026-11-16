import { createRouter, createWebHistory, type RouteRecordRaw } from 'vue-router'
import PhasePlaceholderView from '../views/PhasePlaceholderView.vue'

const routes: RouteRecordRaw[] = [
  { path: '/', redirect: '/stocks' },
  {
    path: '/stocks',
    component: () => import('../features/stocks/views/StockListView.vue'),
    props: { status: 'active' },
  },
  {
    path: '/stocks/add',
    component: () => import('../features/stocks/views/AddStockView.vue'),
  },
  {
    path: '/stocks/archived',
    component: () => import('../features/stocks/views/StockListView.vue'),
    props: { status: 'archived' },
  },
  {
    path: '/stocks/:stockId',
    component: () => import('../features/prices/views/StockDetailView.vue'),
  },
  {
    path: '/stocks/:stockId/analysis/:runId',
    component: () => import('../features/analysis/views/AnalysisRunView.vue'),
  },
  {
    path: '/:pathMatch(.*)*',
    component: PhasePlaceholderView,
    props: { title: '页面不存在', description: '请返回我的股票页面。' },
  },
]

export default createRouter({ history: createWebHistory(), routes })
