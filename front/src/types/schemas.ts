// src/types/schemas.ts
export interface Role {
  id?: number; // Додайте id, якщо бекенд його повертає
  Name: string;
}

export interface Software {
  id?: number; // Додайте id, якщо бекенд його повертає
  name: string; // Залишаємо name для зворотної сумісності
  DisplayName: string; // Додаємо DisplayName для відповідності бекенду
  DisplayVersion?: string;
  InstallDate?: string;
  action?: string;
  is_deleted?: boolean;
}

export interface Disk {
  DeviceID: string;
  TotalSpace: number;
  free_space: number;
}

export enum Status {
  Online = 'online',
  Offline = 'offline',
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

export interface Computer {
  id: string;
  hostname: string;
  ip?: string;
  os_name?: string;
  os_version?: string;
  cpu?: string;
  ram?: number;
  mac?: string;
  motherboard?: string;
  last_boot?: string;
  is_virtual?: boolean;
  status?: string;
  check_status?: string;
  error?: string;
  roles?: Role[];
  software?: Software[];
  disks?: Disk[];
  last_updated?: string;
}

export interface ComputerCreate extends Omit<Computer, 'id' | 'last_updated'> {
  roles: Role[];
  software: Software[];
  disks: Disk[];
}

export interface ChangeLog {
  id: number;
  computer_id: number;
  field: string;
  old_value?: string;
  new_value?: string;
  changed_at: string;
}

export interface ScanTask {
  id: string;
  status: ScanStatus;
  created_at: string;
  updated_at: string;
  scanned_hosts: number;
  successful_hosts: number;
  error?: string;
}

export interface OsStats {
  os_versions: OSStats[];
}

export interface DiskStats {
  low_disk_space: DiskSpaceStats[];
}

export interface ScanStats {
  last_scan_time?: string;
  status_stats: StatusStats[];
}

export interface OSStats {
  os_version: string;
  count: number;
}

export interface DiskSpaceStats {
  hostname: string;
  disk_id: string;
  free_space_percent: number;
}

export interface StatusStats {
  status: string;
  count: number;
}

export interface DashboardStats {
  total_computers: number;
  os_stats: OsStats;
  disk_stats: DiskStats;
  scan_stats: ScanStats;
}