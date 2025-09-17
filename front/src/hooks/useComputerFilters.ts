import { useState, useCallback, useEffect, useMemo } from "react";
import { useSearchParams } from "react-router-dom";
import { useDebounce } from "./useDebounce";
import { ComputerListItem } from "../types/schemas";
import { ITEMS_PER_PAGE } from "../config";
import type { TablePaginationConfig } from "antd";
import type { SorterResult } from "antd/es/table/interface";

export interface Filters {
  hostname: string | undefined;
  os_name: string | undefined;
  domain: string | undefined;
  check_status: string | undefined;
  show_disabled: boolean;
  sort_by: string;
  sort_order: "asc" | "desc";
  page: number;
  limit: number;
  server_filter?: string;
  ip_range?: string;
}

export const isServerOs = (osName: string) => {
  const serverOsPatterns = [/server/i, /hyper-v/i];
  return serverOsPatterns.some((pattern) => pattern.test(osName.toLowerCase()));
};

export const useComputerFilters = (
  cachedComputers: ComputerListItem[],
  domainMap: Map<number, string>,
) => {
  const [searchParams, setSearchParams] = useSearchParams();
  const [filters, setFilters] = useState<Filters>({
    hostname: searchParams.get("hostname") || undefined,
    os_name: searchParams.get("os_name") || undefined,
    domain: searchParams.get("domain") || undefined,
    check_status: searchParams.get("check_status") || undefined,
    show_disabled: searchParams.get("show_disabled") === "true" || false,
    sort_by: searchParams.get("sort_by") || "hostname",
    sort_order: (searchParams.get("sort_order") as "asc" | "desc") || "asc",
    page: Number(searchParams.get("page")) || 1,
    limit: Number(searchParams.get("limit") || ITEMS_PER_PAGE),
    server_filter: searchParams.get("server_filter") || undefined,
    ip_range: searchParams.get("ip_range") || undefined,
  });

  const debouncedFilters = useDebounce(filters, 300);

  // Оновлення параметрів URL при зміні фільтрів
  useEffect(() => {
    setSearchParams(
      (prevParams) => {
        const newParams = new URLSearchParams(prevParams);
        for (const [key, value] of Object.entries(filters)) {
          if (value !== undefined && value !== null && String(value) !== "") {
            if (key === "show_disabled" && value === false) {
              newParams.delete(key);
            } else {
              newParams.set(key, String(value));
            }
          } else {
            newParams.delete(key);
          }
        }
        return newParams;
      },
      { replace: true },
    );
  }, [filters, setSearchParams]);

  // Обробка зміни фільтрів
  const handleFilterChange = useCallback(
    (key: keyof Filters, value: string | boolean | undefined) => {
      setFilters((prev) => ({
        ...prev,
        [key]: value,
        page: key !== "page" ? 1 : prev.page,
      }));
    },
    [],
  );

  // Очищення всіх фільтрів
  const clearAllFilters = useCallback(() => {
    setFilters({
      hostname: undefined,
      os_name: undefined,
      domain: undefined,
      check_status: undefined,
      show_disabled: false,
      sort_by: "hostname",
      sort_order: "asc",
      page: 1,
      limit: ITEMS_PER_PAGE,
      server_filter: undefined,
      ip_range: undefined,
    });
  }, []);

  // Обробка зміни таблиці (сортування, пагінація)
  const handleTableChange = useCallback(
    (
      pagination: TablePaginationConfig,
      _filters: Record<string, any>,
      sorter: SorterResult<ComputerListItem> | SorterResult<ComputerListItem>[],
    ) => {
      const sort = Array.isArray(sorter) ? sorter[0] : sorter;
      setFilters((prev) => ({
        ...prev,
        page: pagination.current || 1,
        limit: pagination.pageSize || ITEMS_PER_PAGE,
        sort_by: sort.field ? String(sort.field) : prev.sort_by,
        sort_order:
          sort.order === "ascend"
            ? "asc"
            : sort.order === "descend"
              ? "desc"
              : prev.sort_order,
      }));
    },
    [],
  );

  // Уніфікована функція для отримання значення для сортування
  const getSortValue = (
    comp: ComputerListItem,
    field: keyof ComputerListItem | string,
    domainMap: Map<number, string>,
  ) => {
    if (field === "ip_addresses") return comp.ip_addresses?.[0]?.address || "";
    if (field === "os") return comp.os?.name?.toLowerCase() || "";
    //if (field === 'is_virtual') return comp.is_virtual ?? false;
    //if (field === 'physical_disks') return comp.physical_disks?.[0]?.model || '';
    //if (field === 'logical_disks') return comp.logical_disks?.[0]?.volume_label || '';
    //if (field === 'processors') return comp.processors?.[0]?.name || '';
    //if (field === 'mac_addresses') return comp.mac_addresses?.[0]?.address || '';
    //if (field === 'roles') return comp.roles?.[0]?.Name || '';
    //if (field === 'software') return comp.software?.[0]?.DisplayName || '';
    //if (field === 'video_cards') return comp.video_cards?.[0]?.name || '';
    if (field === "last_full_scan")
      return comp.last_full_scan ? new Date(comp.last_full_scan) : new Date(0);
    if (field === "domain_id")
      return comp.domain_id ? (domainMap.get(comp.domain_id) ?? "") : "";
    return comp[field as keyof ComputerListItem] ?? "";
  };

  // Фільтрація комп’ютерів на клієнтській стороні
  const filteredComputers = useMemo(() => {
    let filtered = [...cachedComputers];

    // Застосовуємо фільтри
    filtered = filtered.filter((comp) => {
      const domainName = comp.domain_id
        ? domainMap.get(comp.domain_id)?.toLowerCase()
        : "";
      const showDisabledFilter =
        debouncedFilters.show_disabled ||
        (comp.check_status !== "disabled" &&
          comp.check_status !== "is_deleted");

      const hostnameFilter =
        !debouncedFilters.hostname ||
        comp.hostname
          ?.toLowerCase()
          .includes(debouncedFilters.hostname.toLowerCase());
      const osNameFilter =
        !debouncedFilters.os_name ||
        comp.os?.name
          ?.toLowerCase()
          .includes(debouncedFilters.os_name.toLowerCase());
      const domainFilter =
        !debouncedFilters.domain ||
        domainName === debouncedFilters.domain.toLowerCase();
      const checkStatusFilter =
        !debouncedFilters.check_status ||
        comp.check_status === debouncedFilters.check_status;
      const serverFilter =
        !debouncedFilters.server_filter ||
        (debouncedFilters.server_filter === "server" &&
          comp.os?.name &&
          isServerOs(comp.os.name)) ||
        (debouncedFilters.server_filter === "client" &&
          comp.os?.name &&
          !isServerOs(comp.os.name));
      const ipRangeFilter =
        !debouncedFilters.ip_range ||
        comp.ip_addresses?.some((ip) => {
          const ipParts = ip.address.split(".");
          const rangeParts = debouncedFilters.ip_range!.split(".");
          if (rangeParts[2]?.startsWith("[")) {
            const [start, end] = rangeParts[2]
              .match(/\[(\d+)-(\d+)\]/)!
              .slice(1)
              .map(Number);
            const thirdOctet = Number(ipParts[2]);
            return (
              ipParts[0] === rangeParts[0] &&
              ipParts[1] === rangeParts[1] &&
              thirdOctet >= start &&
              thirdOctet <= end
            );
          }
          return ip.address === debouncedFilters.ip_range;
        });

      return (
        showDisabledFilter &&
        hostnameFilter &&
        osNameFilter &&
        domainFilter &&
        checkStatusFilter &&
        serverFilter &&
        ipRangeFilter
      );
    });

    // Сортування
    filtered.sort((a, b) => {
      const aValue = getSortValue(a, filters.sort_by, domainMap);
      const bValue = getSortValue(b, filters.sort_by, domainMap);

      if (typeof aValue === "boolean" && typeof bValue === "boolean") {
        return filters.sort_order === "asc"
          ? aValue === bValue
            ? 0
            : aValue
              ? 1
              : -1
          : aValue === bValue
            ? 0
            : aValue
              ? -1
              : 1;
      }
      if (aValue instanceof Date && bValue instanceof Date) {
        return filters.sort_order === "asc"
          ? aValue.getTime() - bValue.getTime()
          : bValue.getTime() - aValue.getTime();
      }
      return filters.sort_order === "asc"
        ? String(aValue).localeCompare(String(bValue))
        : String(bValue).localeCompare(String(aValue));
    });

    // Пагінація
    const start = (filters.page - 1) * filters.limit;
    const end = start + filters.limit;
    return {
      data: filtered.slice(start, end),
      total: filtered.length,
    };
  }, [
    cachedComputers,
    debouncedFilters,
    filters.sort_by,
    filters.sort_order,
    filters.page,
    filters.limit,
    domainMap,
  ]);

  return {
    filters,
    filteredComputers,
    debouncedSetHostname: handleFilterChange.bind(null, "hostname"),
    handleFilterChange,
    clearAllFilters,
    handleTableChange,
  };
};
