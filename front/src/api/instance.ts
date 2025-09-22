// front/src/api/instance.ts
import axios from "axios";
import { API_URL } from '../config';

export const apiInstance = axios.create({
  baseURL: API_URL,
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