// front/src/api/instance.ts
import axios from "axios";

export const apiInstance = axios.create({
  baseURL: import.meta.env.VITE_API_URL || "http://localhost:8000/api",
  withCredentials: true, 
});

apiInstance.interceptors.request.use((config) => {
  return config;
});

apiInstance.interceptors.response.use(
  (response) => {
    return response;
  },
  (error) => {
    console.error(`Response error: ${error.response?.status} for ${error.config?.url}`, error.response?.data);
    return Promise.reject(error);
  }
);