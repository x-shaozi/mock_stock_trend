import { http } from './http'

export interface HealthResponse {
  status: 'ok'
}

export async function getHealth(): Promise<HealthResponse> {
  const response = await http.get<HealthResponse>('/health')
  return response.data
}
