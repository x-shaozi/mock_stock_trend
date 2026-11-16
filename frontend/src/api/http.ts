import axios from 'axios'
import { ApiRequestError, extractApiErrorPayload } from './errors'

export const http = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL || '/api',
  timeout: 15_000,
})

http.interceptors.response.use(
  (response) => response,
  (error: unknown) => {
    if (!axios.isAxiosError(error)) return Promise.reject(error)
    if (error.code === 'ERR_CANCELED') {
      return Promise.reject(
        new ApiRequestError('请求已取消', undefined, undefined, undefined, 'aborted'),
      )
    }
    if (error.code === 'ECONNABORTED' || error.code === 'ETIMEDOUT') {
      return Promise.reject(
        new ApiRequestError('请求超时', undefined, undefined, undefined, 'timeout'),
      )
    }
    if (!error.response) {
      return Promise.reject(
        new ApiRequestError(
          '无法连接股票分析服务，请检查后端是否已启动',
          undefined,
          undefined,
          undefined,
          'network',
        ),
      )
    }
    const payload = extractApiErrorPayload(error.response.data)
    const status = error.response.status
    // FastAPI 的统一 500 会带 code/message；Vite 代理连不上后端时可能只返回空 500。
    // 没有业务内容的 500 按连接异常处理，使页面提示检查后端，并允许 GET 有限重试。
    if (
      status === 500 &&
      payload?.code === undefined &&
      payload?.message === undefined &&
      payload?.error_code === undefined &&
      payload?.errors === undefined
    ) {
      return Promise.reject(
        new ApiRequestError('未收到后端业务响应', status, undefined, undefined, 'network'),
      )
    }
    // Vite 代理 502 往往没有业务 JSON，不能误称为第三方行情网站故障。
    const fallback = status >= 500 ? '服务暂时不可用，请稍后重试' : '请求失败'
    return Promise.reject(
      new ApiRequestError(
        payload?.message || fallback,
        status,
        payload?.error_code || undefined,
        payload?.errors || undefined,
      ),
    )
  },
)

// 成功响应直接由各业务 API 读取 response.data，无统一 data 外壳。
