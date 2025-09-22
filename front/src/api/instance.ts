// src/api/instance.ts
import axios from "axios";

export const apiInstance = axios.create({
  baseURL: `http://${window.location.hostname}:8000/api`,
  //baseURL: "/api",
  withCredentials: true,
});