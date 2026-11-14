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
    const payload = extractApiErrorPayload(error.response?.data)
    const message = payload?.message || (error.response ? '请求失败' : '无法连接后端服务')
    return Promise.reject(
      new ApiRequestError(
        message,
        error.response?.status,
        payload?.error_code || undefined,
        payload?.errors || undefined,
      ),
    )
  },
)

// 成功响应不含通用 data 包装：由具体 API 方法读取 response.data。
