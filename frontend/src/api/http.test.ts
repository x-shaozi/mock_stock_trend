import { AxiosError, type AxiosResponse, type InternalAxiosRequestConfig } from 'axios'
import { describe, expect, it } from 'vitest'
import { describeRequestError } from './errors'
import { http } from './http'

// 用 Axios 自带的替身请求模拟 Vite 或后端响应，不访问真实服务。
function serverError(data: unknown) {
  return async (config: InternalAxiosRequestConfig) => {
    const response: AxiosResponse = {
      data,
      status: 500,
      statusText: 'Internal Server Error',
      headers: {},
      config,
    }
    throw new AxiosError(
      'Request failed with status code 500',
      'ERR_BAD_RESPONSE',
      config,
      undefined,
      response,
    )
  }
}

describe('HTTP 错误识别', () => {
  it('代理返回空的 500 时提示连接异常', async () => {
    try {
      await http.get('/stocks/10', { adapter: serverError('') })
      throw new Error('预期请求失败')
    } catch (error: unknown) {
      expect(describeRequestError(error).title).toBe('无法连接股票分析服务')
    }
  })

  it('后端返回业务 JSON 的 500 时保留服务端异常提示', async () => {
    try {
      await http.get('/stocks/10', {
        adapter: serverError({ code: 500, message: '服务器内部错误' }),
      })
      throw new Error('预期请求失败')
    } catch (error: unknown) {
      expect(describeRequestError(error).title).toBe('股票分析服务暂时异常')
    }
  })
})
