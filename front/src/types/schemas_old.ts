// src/types/schemas.ts

export interface Role {
  id?: number; // ID возвращается бэкендом
  name: string; // Соответствует полю 'name' в Pydantic
}

export interface Software {
  id?: number; // ID возвращается бэкендом
  name: string; // Соответствует 'DisplayName' в Pydantic
  version?: string; // Соответствует 'DisplayVersion'
  install_date?: string; // ISO 8601 формат даты
  action?: string; // 'Installed' или 'Uninstalled'
  is_deleted: boolean; // Соответствует полю в модели
}

export interface Disk {
  id?: number; // ID возвращается бэкендом
  device_id: string; // Соответствует 'DeviceID'
  total_space: number; // Соответствует 'TotalSpace'
  free_space: number; // Соответствует 'FreeSpace'
}

export enum CheckStatus {
  Success = 'success',
  Failed = 'failed',
  Unreachable = 'unreachable',
}

export enum ScanStatus {
  Pending = 'pending',
  Running = 'running',
  Completed = 'completed',
  Failed = 'failed',
}

export interface ComputerBase {
  hostname: string;
  ip?: string;
  os_name?: string;
  os_version?: string;
  cpu?: string;
  ram?: number;
  mac?: string;
  motherboard?: string;
  last_boot?: string; // ISO 8601 формат даты
  is_virtual?: boolean;
  check_status?: CheckStatus;
}

export interface ComputerList extends ComputerBase {
  id: number; // Integer в модели, возвращается бэкендом
  last_updated: string; // ISO 8601 формат даты
}

export interface Computer extends ComputerBase {
  id: number; // Integer в модели
  last_updated: string; // ISO 8601 формат даты
  roles: Role[];
  software: Software[];
  disks: Disk[];
}

export interface ComputerCreate extends Omit<Computer, 'id' | 'last_updated'> {
  roles: Role[];
  software: Software[];
  disks: Disk[];
}

export interface ComputersResponse {
  data: ComputerList[];
  total: number;
}

export interface ChangeLog {
  id: number;
  computer_id: number;
  field: string;
  old_value?: string;
  new_value?: string;
  changed_at: string; // ISO 8601 формат даты
}

export interface ScanTask {
  id: string;
  status: ScanStatus;
  created_at: string; // ISO 8601 формат даты
  updated_at: string; // ISO 8601 формат даты
  scanned_hosts: number;
  successful_hosts: number;
  error?: string;
}

export interface OsVersion {
  os_version?: string;
  count: number;
}

export interface LowDiskSpace {
  hostname: string;
  disk_id: string;
  free_space_percent: number;
}

export interface StatusStats {
  status: CheckStatus;
  count: number;
}

export interface OsStats {
  os_versions: OsVersion[];
}

export interface DiskStats {
  low_disk_space: LowDiskSpace[];
}

export interface ScanStats {
  last_scan_time?: string; // ISO 8601 формат даты
  status_stats: StatusStats[];
}

export interface DashboardStats {
  total_computers?: number;
  os_stats: OsStats;
  disk_stats: DiskStats;
  scan_stats: ScanStats;
}
