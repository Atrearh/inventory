// Auto-generated TypeScript types

/* tslint:disable */

/**
/* This file was automatically generated from pydantic models by running pydantic2ts.
/* Do not modify it by hand - just update the pydantic models and then re-run the script
*/

export type CheckStatus =
  | "success"
  | "failed"
  | "unreachable"
  | "partially_successful"
  | "disabled"
  | "is_deleted";
export type ScanStatus = "pending" | "running" | "completed" | "failed";

export interface AppSettingUpdate {
  ad_server_url?: string | null;
  domain?: string | null;
  ad_username?: string | null;
  ad_password?: string | null;
  api_url?: string | null;
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
  encryption_key?: string | null;
  timezone?: string | null;
}
export interface BaseSchema {}
export interface ComponentChangeStats {
  component_type: string;
  changes_count: number;
}
export interface ComponentHistory {
  component_type: string;
  data:
    | PhysicalDisk
    | LogicalDisk
    | Processor
    | VideoCard
    | IPAddress
    | MACAddress
    | InstalledSoftwareRead
    | Role;
  detected_on?: string | null;
  removed_on?: string | null;
}
export interface PhysicalDisk {
  detected_on?: string | null;
  removed_on?: string | null;
  id?: number | null;
  computer_id: number;
  model?: string | null;
  serial?: string | null;
  interface?: string | null;
  media_type?: string | null;
}
export interface LogicalDisk {
  detected_on?: string | null;
  removed_on?: string | null;
  device_id?: string | null;
  volume_label?: string | null;
  total_space: number;
  free_space?: number | null;
  parent_disk_serial?: string | null;
}
export interface Processor {
  detected_on?: string | null;
  removed_on?: string | null;
  Name: string;
  NumberOfCores?: number | null;
  NumberOfThreads?: number | null;
  MaxClockSpeed?: number | null;
}
export interface VideoCard {
  detected_on?: string | null;
  removed_on?: string | null;
  Name: string;
  AdapterRAM?: number | null;
}
export interface IPAddress {
  detected_on?: string | null;
  removed_on?: string | null;
  address: string;
}
export interface MACAddress {
  detected_on?: string | null;
  removed_on?: string | null;
  address: string;
}
export interface InstalledSoftwareRead {
  name: string;
  version?: string | null;
  publisher?: string | null;
  install_date?: string | null;
}
export interface Role {
  detected_on?: string | null;
  removed_on?: string | null;
  Name: string;
}
export interface ComponentSchema {
  detected_on?: string | null;
  removed_on?: string | null;
}
export interface ComputerCore {
  hostname: string;
  os?: OperatingSystemRead | null;
  ram?: number | null;
  motherboard?: string | null;
  last_boot?: string | null;
  is_virtual?: boolean | null;
  check_status?: CheckStatus | null;
}
export interface OperatingSystemRead {
  name: string;
  version?: string | null;
  architecture?: string | null;
}
export interface ComputerCreate {
  hostname: string;
  os?: OperatingSystemRead | null;
  ram?: number | null;
  motherboard?: string | null;
  last_boot?: string | null;
  is_virtual?: boolean | null;
  check_status?: CheckStatus | null;
  ip_addresses?: IPAddress[];
  mac_addresses?: MACAddress[];
  processors?: Processor[];
  video_cards?: VideoCard[];
  software?: InstalledSoftwareRead[];
  roles?: Role[];
  physical_disks?: PhysicalDisk[];
  logical_disks?: LogicalDisk[];
}
export interface ComputerDetail {
  hostname: string;
  os?: OperatingSystemRead | null;
  ram?: number | null;
  motherboard?: string | null;
  last_boot?: string | null;
  is_virtual?: boolean | null;
  check_status?: CheckStatus | null;
  id: number;
  last_updated?: string | null;
  last_full_scan?: string | null;
  domain_id?: number | null;
  domain_name?: string | null;
  object_guid?: string | null;
  when_created?: string | null;
  when_changed?: string | null;
  enabled?: boolean | null;
  ad_notes?: string | null;
  local_notes?: string | null;
  last_logon?: string | null;
  ip_addresses?: IPAddress[];
  mac_addresses?: MACAddress[];
  processors?: Processor[];
  video_cards?: VideoCard[];
  software?: InstalledSoftwareRead[];
  roles?: Role[];
  physical_disks?: PhysicalDisk[];
  logical_disks?: LogicalDisk[];
}
export interface ComputerListItem {
  hostname: string;
  os?: OperatingSystemRead | null;
  ram?: number | null;
  motherboard?: string | null;
  last_boot?: string | null;
  is_virtual?: boolean | null;
  check_status?: CheckStatus | null;
  id: number;
  last_updated?: string | null;
  last_full_scan?: string | null;
  domain_id?: number | null;
  domain_name?: string | null;
  ip_addresses?: IPAddress[];
}
export interface ComputerUpdateCheckStatus {
  hostname: string;
  check_status: CheckStatus;
}
export interface ComputersResponse {
  data: ComputerListItem[];
  total: number;
}
export interface DashboardStats {
  total_computers?: number | null;
  os_stats: OsStats;
  disk_stats: DiskStats;
  scan_stats: ScanStats;
  component_changes?: ComponentChangeStats[];
}
export interface OsStats {
  client_os?: OsCategoryStats[];
  server_os?: OsCategoryStats[];
  os_name?: string | null;
  count: number;
  software_distribution?: OsCategoryStats[];
}
export interface OsCategoryStats {
  category: string;
  count: number;
}
export interface DiskStats {
  low_disk_space: DiskVolume[];
}
export interface DiskVolume {
  id: number;
  hostname: string;
  device_id: string;
  volume_label?: string | null;
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
export interface DomainBase {
  name: string;
  username: string;
  password: string;
  server_url: string;
  ad_base_dn: string;
  id: number;
  last_updated?: string | null;
}
export interface DomainCore {
  name: string;
  username: string;
  password: string;
  server_url: string;
  ad_base_dn: string;
}
export interface DomainCreate {
  name: string;
  username: string;
  password: string;
  server_url: string;
  ad_base_dn: string;
}
export interface DomainRead {
  name: string;
  username: string;
  server_url: string;
  ad_base_dn: string;
  id: number;
  last_updated?: string | null;
}
export interface DomainUpdate {
  id: number;
  last_updated?: string | null;
  name?: string | null;
  username?: string | null;
  password?: string | null;
  server_url?: string | null;
  ad_base_dn?: string | null;
}
export interface ErrorResponse {
  error: string;
  detail?: string | null;
  correlation_id?: string | null;
}
export interface ScanResponse {
  status: string;
  task_id: string;
}
export interface ScanTask {
  id: string;
  status: ScanStatus;
  scanned_hosts: number;
  successful_hosts: number;
  error: string | null;
  created_at: string;
  updated_at: string;
  progress?: number;
  name?: string | null;
}
export interface SessionRead {
  id: number;
  issued_at: string;
  expires_at: string;
  is_current?: boolean;
}
export interface TaskRead {
  id: string;
  name: string;
  status: string;
  created_at: string;
}
export interface TrackableComponent {
  detected_on?: string | null;
  removed_on?: string | null;
}
export interface UserCreate {
  email: string;
  password: string;
  is_active?: boolean | null;
  is_superuser?: boolean | null;
  is_verified?: boolean | null;
  username: string;
  role?: string | null;
}
export interface UserRead {
  id: number;
  email: string;
  is_active?: boolean;
  is_superuser?: boolean;
  is_verified?: boolean;
  username: string;
  role?: string | null;
}
export interface UserUpdate {
  password?: string | null;
  email?: string | null;
  is_active?: boolean | null;
  is_superuser?: boolean | null;
  is_verified?: boolean | null;
  username?: string | null;
  role?: string | null;
}
