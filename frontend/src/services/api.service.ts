import axios, {
  AxiosInstance,
  AxiosRequestConfig,
  AxiosResponse,
  AxiosError,
} from 'axios';
import * as SecureStore from 'expo-secure-store';
import { API_BASE_URL, API_TIMEOUT, STORAGE_KEYS } from '../constants';
import { ApiResponse, ApiError } from '../types';

class ApiService {
  private axiosInstance: AxiosInstance;
  private isRefreshing = false;
  private failedQueue: Array<{
    resolve: (value?: any) => void;
    reject: (reason?: any) => void;
  }> = [];

  constructor() {
    this.axiosInstance = axios.create({
      baseURL: API_BASE_URL,
      timeout: API_TIMEOUT,
      headers: {
        'Content-Type': 'application/json',
      },
    });

    this.setupInterceptors();
  }

  private setupInterceptors(): void {
    // Request Interceptor
    this.axiosInstance.interceptors.request.use(
      async config => {
        const token = await SecureStore.getItemAsync(STORAGE_KEYS.AUTH_TOKEN);
        if (token) {
          config.headers.Authorization = `Bearer ${token}`;
        }
        console.log(`API Request: ${config.method?.toUpperCase()} ${config.baseURL}${config.url}`);
        return config;
      },
      error => {
        return Promise.reject(error);
      },
    );

    // Response Interceptor
    this.axiosInstance.interceptors.response.use(
      response => response,
      async (error: AxiosError) => {
        const originalRequest = error.config as AxiosRequestConfig & {
          _retry?: boolean;
        };

        if (error.response?.status === 401 && !originalRequest._retry) {
          if (this.isRefreshing) {
            return new Promise((resolve, reject) => {
              this.failedQueue.push({ resolve, reject });
            })
              .then(token => {
                if (originalRequest.headers) {
                  originalRequest.headers.Authorization = `Bearer ${token}`;
                }
                return this.axiosInstance(originalRequest);
              })
              .catch(err => {
                return Promise.reject(err);
              });
          }

          originalRequest._retry = true;
          this.isRefreshing = true;

          try {
            const refreshToken = await SecureStore.getItemAsync(
              STORAGE_KEYS.REFRESH_TOKEN,
            );

            if (!refreshToken) {
              throw new Error('No refresh token');
            }

            const response = await this.axiosInstance.post('/auth/refresh', {
              refreshToken,
            });

            const { accessToken } = response.data.data;
            await SecureStore.setItemAsync(
              STORAGE_KEYS.AUTH_TOKEN,
              accessToken,
            );

            this.processQueue(null, accessToken);
            this.failedQueue = [];

            if (originalRequest.headers) {
              originalRequest.headers.Authorization = `Bearer ${accessToken}`;
            }

            return this.axiosInstance(originalRequest);
          } catch (refreshError) {
            this.processQueue(refreshError, null);
            this.failedQueue = [];
            await this.clearAuthData();
            return Promise.reject(refreshError);
          } finally {
            this.isRefreshing = false;
          }
        }

        return Promise.reject(this.handleError(error));
      },
    );
  }

  private processQueue(error: any, token: string | null = null): void {
    this.failedQueue.forEach(prom => {
      if (error) {
        prom.reject(error);
      } else {
        prom.resolve(token);
      }
    });
  }

  private handleError(error: AxiosError): ApiError {
    if (error.response) {
      return {
        message: (error.response.data as any)?.message || 'An error occurred',
        statusCode: error.response.status,
        errors: (error.response.data as any)?.errors,
      };
    } else if (error.request) {
      return {
        message: 'Network error. Please check your internet connection.',
      };
    } else {
      return {
        message: error.message || 'An unexpected error occurred',
      };
    }
  }

  private async clearAuthData(): Promise<void> {
    await SecureStore.deleteItemAsync(STORAGE_KEYS.AUTH_TOKEN);
    await SecureStore.deleteItemAsync(STORAGE_KEYS.REFRESH_TOKEN);
    await SecureStore.deleteItemAsync(STORAGE_KEYS.USER_DATA);
  }

  // Generic HTTP Methods
  async get<T>(
    url: string,
    config?: AxiosRequestConfig,
  ): Promise<ApiResponse<T>> {
    try {
      const response: AxiosResponse<ApiResponse<T>> =
        await this.axiosInstance.get(url, config);
      return response.data;
    } catch (error) {
      throw error;
    }
  }

  async post<T>(
    url: string,
    data?: any,
    config?: AxiosRequestConfig,
  ): Promise<ApiResponse<T>> {
    try {
      const response: AxiosResponse<ApiResponse<T>> =
        await this.axiosInstance.post(url, data, config);
      return response.data;
    } catch (error) {
      throw error;
    }
  }

  async put<T>(
    url: string,
    data?: any,
    config?: AxiosRequestConfig,
  ): Promise<ApiResponse<T>> {
    try {
      const response: AxiosResponse<ApiResponse<T>> =
        await this.axiosInstance.put(url, data, config);
      return response.data;
    } catch (error) {
      throw error;
    }
  }

  async patch<T>(
    url: string,
    data?: any,
    config?: AxiosRequestConfig,
  ): Promise<ApiResponse<T>> {
    try {
      const response: AxiosResponse<ApiResponse<T>> =
        await this.axiosInstance.patch(url, data, config);
      return response.data;
    } catch (error) {
      throw error;
    }
  }

  async delete<T>(
    url: string,
    config?: AxiosRequestConfig,
  ): Promise<ApiResponse<T>> {
    try {
      const response: AxiosResponse<ApiResponse<T>> =
        await this.axiosInstance.delete(url, config);
      return response.data;
    } catch (error) {
      throw error;
    }
  }

  // File Upload
  async uploadFile<T>(
    url: string,
    formData: FormData,
    onUploadProgress?: (progressEvent: any) => void,
  ): Promise<ApiResponse<T>> {
    try {
      const response: AxiosResponse<ApiResponse<T>> =
        await this.axiosInstance.post(url, formData, {
          headers: {
            'Content-Type': 'multipart/form-data',
          },
          onUploadProgress,
        });
      return response.data;
    } catch (error) {
      throw error;
    }
  }
}

export default new ApiService();
