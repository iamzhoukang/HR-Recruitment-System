import axios, { type AxiosInstance, type AxiosRequestConfig } from 'axios'
import { useUserStore } from '@/stores/user'

class HttpRequest {
  private instance: AxiosInstance
  public baseURL: string

  constructor() {
    // TODO: Add your API base URL here
    const baseURL = import.meta.env.VITE_API_BASE_URL
    this.baseURL = baseURL

    this.instance = axios.create({
      baseURL,
      timeout: 300000,
    })

    this.initializeInterceptors()
  }

  private initializeInterceptors() {
    // Request interceptor
    this.instance.interceptors.request.use(
      (config) => {
        const userStore = useUserStore()
        const token = userStore.accessToken
        console.log('token: ', token)
        if (token) {
          config.headers.Authorization = `Bearer ${token}`
        }
        return config
      },
      (error) => {
        return Promise.reject(error)
      },
    )

    // Response interceptor
    this.instance.interceptors.response.use(
      (response) => {
        return response
      },
      (error) => {
        // TODO: Add global error handling
        return Promise.reject(error)
      },
    )
  }

  public request<T = any>(config: AxiosRequestConfig): Promise<T> {
    return this.instance.request<T>(config).then((response) => response.data)
  }

  public get<T = any>(url: string, params?: object, config?: AxiosRequestConfig): Promise<T> {
    return this.request({ ...config, url, method: 'GET', params })
  }

  public post<T = any>(url: string, data?: object, config?: AxiosRequestConfig): Promise<T> {
    return this.request({ ...config, url, method: 'POST', data })
  }

  public put<T = any>(url: string, data?: object, config?: AxiosRequestConfig): Promise<T> {
    return this.request({ ...config, url, method: 'PUT', data })
  }

  public delete<T = any>(url: string, config?: AxiosRequestConfig): Promise<T> {
    return this.request({ ...config, url, method: 'DELETE' })
  }

  public patch<T = any>(url: string, data?: object, config?: AxiosRequestConfig): Promise<T> {
    return this.request({ ...config, url, method: 'PATCH', data })
  }

  public upload<T = any>(url: string, formData: FormData, config?: AxiosRequestConfig): Promise<T> {
    return this.request({
      ...config,
      url,
      method: 'POST',
      data: formData,
      headers: {
        ...config?.headers,
        'Content-Type': 'multipart/form-data',
      },
    })
  }
}

export default new HttpRequest()
