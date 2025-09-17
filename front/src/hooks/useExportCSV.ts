// src/hooks/useExportCSV.ts
import { useCallback } from "react";
import { notification } from "antd";
import { apiInstance } from "../api/api";
import { Filters } from "./useComputerFilters";

export const useExportCSV = (filters: Filters) => {
  const handleExportCSV = useCallback(async () => {
    try {
      const cleanedParams = {
        hostname: filters.hostname || undefined,
        os_name: filters.os_name || undefined,
        check_status:
          filters.check_status === "is_deleted"
            ? undefined
            : filters.check_status || undefined,
        sort_by: filters.sort_by || "hostname",
        sort_order:
          filters.sort_order === "asc" || filters.sort_order === "desc"
            ? filters.sort_order
            : "asc",
        server_filter: filters.server_filter || undefined,
      };

      const response = await apiInstance.get("/computers/export/csv", {
        params: cleanedParams,
        responseType: "blob",
        paramsSerializer: (params) => {
          const searchParams = new URLSearchParams();
          for (const [key, value] of Object.entries(params)) {
            if (value !== undefined && value !== "") {
              searchParams.append(key, String(value));
            }
          }
          return searchParams.toString();
        },
      });

      const currentDate = new Date().toISOString().split("T")[0];
      const filename = `computers_${currentDate}.csv`;

      const url = window.URL.createObjectURL(new Blob([response.data]));
      const link = document.createElement("a");
      link.href = url;
      link.setAttribute("download", filename);
      document.body.appendChild(link);
      link.click();
      document.body.removeChild(link);
      window.URL.revokeObjectURL(url);

      notification.success({
        message: "Успех",
        description: "Файл CSV успешно скачан",
      });
    } catch (error: any) {
      notification.error({
        message: "Ошибка",
        description: `Не удалось экспортировать данные в CSV: ${error.response?.data?.detail || error.message}`,
      });
    }
  }, [filters]);

  return { handleExportCSV };
};
