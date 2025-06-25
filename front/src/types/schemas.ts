/* tslint:disable */
/* eslint-disable */
/**
/* This file was automatically generated from pydantic models by running pydantic2ts.
/* Do not modify it by hand - just update the pydantic models and then re-run the script
*/

export type CheckStatus = "success" | "failed" | "unreachable";
export type ScanStatus = "pending" | "running" | "completed" | "failed";

export interface AppSettingUpdate {
  ad_server_url?: string | null;
  domain?: string | null;
  ad_username?: string | null;
  ad_password?: string | null;
  api_url?: string | null;
  test_hosts?: string | null;
  log_level?: string | null;
  scan_max_workers?: number | null;
  polling_days_threshold?: number | null;
  winrm_operation_timeout?: number | null;
  winrm_read_timeout?: number | null;
  winrm_port?: number | null;
  winrm_server_cert_validation?: string | null;
  ping_timeout?: number | null;
  powershell_encoding?: string | null;
  json_depth?: number | null;
  server_port?: number | null;
  cors_allow_origins?: string | null;
  allowed_ips?: string | null;
}
export interface ChangeLog {
  id: number;
  computer_id: number;
  field: string;
  old_value?: string | null;
  new_value?: string | null;
  changed_at: string;
}
export interface Computer {
  hostname: string;
  ip?: string | null;
  os_name?: string | null;
  os_version?: string | null;
  cpu?: string | null;
  ram?: number | null;
  mac?: string | null;
  motherboard?: string | null;
  last_boot?: string | null;
  is_virtual?: boolean | null;
  check_status?: CheckStatus | null;
  id: number;
  last_updated: string;
  disks?: Disk[];
  roles?: Role[];
  software?: Software[];
}
export interface Disk {
  DeviceID?: string | null;
  TotalSpace: number;
  FreeSpace?: number | null;
}
export interface Role {
  Name: string;
}
export interface Software {
  DisplayName: string;
  DisplayVersion?: string | null;
  InstallDate?: string | null;
  Action?: string | null;
  is_deleted?: boolean;
}
export interface ComputerBase {
  hostname: string;
  ip?: string | null;
  os_name?: string | null;
  os_version?: string | null;
  cpu?: string | null;
  ram?: number | null;
  mac?: string | null;
  motherboard?: string | null;
  last_boot?: string | null;
  is_virtual?: boolean | null;
  check_status?: CheckStatus | null;
}
export interface ComputerCreate {
  hostname: string;
  ip?: string | null;
  os_name?: string | null;
  os_version?: string | null;
  cpu?: string | null;
  ram?: number | null;
  mac?: string | null;
  motherboard?: string | null;
  last_boot?: string | null;
  is_virtual?: boolean | null;
  check_status?: CheckStatus | null;
  roles?: Role[];
  software?: Software[];
  disks?: Disk[];
}
export interface ComputerList {
  hostname: string;
  ip?: string | null;
  os_name?: string | null;
  os_version?: string | null;
  cpu?: string | null;
  ram?: number | null;
  mac?: string | null;
  motherboard?: string | null;
  last_boot?: string | null;
  is_virtual?: boolean | null;
  check_status?: CheckStatus | null;
  id: number;
  last_updated: string;
}
export interface ComputerUpdateCheckStatus {
  hostname: string;
  check_status: CheckStatus;
}
export interface ComputersResponse {
  data: ComputerList[];
  total: number;
}
export interface DashboardStats {
  total_computers: number | null;
  os_stats: OsStats;
  disk_stats: DiskStats;
  scan_stats: ScanStats;
  os_names?: string[];
}
export interface OsStats {
  client_os: OsDistribution[];
  server_os: ServerDistribution[];
}
export interface OsDistribution {
  category: string;
  count: number;
}
export interface ServerDistribution {
  category: string;
  count: number;
}
export interface DiskStats {
  low_disk_space: DiskVolume[];
}
export interface DiskVolume {
  hostname: string;
  disk_id: string;
  total_space_gb: number;
  free_space_gb: number;
}
export interface ScanStats {
  last_scan_time: string | null;
  status_stats: StatusStats[];
}
export interface StatusStats {
  status: CheckStatus;
  count: number;
}
export interface ErrorResponse {
  error: string;
  detail?: string | null;
  correlation_id?: string | null;
}
export interface ScanTask {
  id: string;
  status: ScanStatus;
  created_at: string;
  updated_at: string;
  scanned_hosts: number;
  successful_hosts: number;
  error?: string | null;
}
