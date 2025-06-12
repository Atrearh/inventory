// src/types/schemas.ts
export interface Role {
  Name: string;
}

export interface Software {
  DisplayName: string;
  DisplayVersion?: string;
  InstallDate?: string;
}

export interface Disk {
  DeviceID: string;
  TotalSpace: number;
  FreeSpace: number;
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
export interface OSStats {
  os_version: string;
  count: number;
}

export interface DiskSpaceStats {
  hostname: string;
  disk_id: string;
  free_space_percent: number;
}

export interface DashboardStats {
  total_computers: number;
  os_versions: OSStats[];
  low_disk_space: DiskSpaceStats[];
  last_scan_time?: string;
}