/* tslint:disable */
/* eslint-disable */
/**
/* This file was automatically generated from pydantic models by running pydantic2ts.
/* Do not modify it by hand - just update the pydantic models and then re-run the script
*/

export type CheckStatus = "success" | "failed" | "unreachable" | "partially_successful";
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
  encryption_key?: string | null;
}
export interface BaseSchema {}
export interface ComponentChangeStats {
  component_type: string;
  changes_count: number;
}
export interface ComponentHistory {
  component_type: string;
  data: PhysicalDisk | LogicalDisk | Processor | VideoCard | IPAddress | MACAddress | Software;
  detected_on?: string | null;
  removed_on?: string | null;
}
export interface PhysicalDisk {
  detected_on?: string | null;
  removed_on?: string | null;
  id?: number | null;
  computer_id?: number | null;
  model?: string | null;
  serial: string;
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
  name: string;
  number_of_cores: number;
  number_of_logical_processors: number;
}
export interface VideoCard {
  detected_on?: string | null;
  removed_on?: string | null;
  id?: number | null;
  name: string;
  driver_version?: string | null;
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
export interface Software {
  detected_on?: string | null;
  removed_on?: string | null;
  DisplayName: string;
  DisplayVersion?: string | null;
  InstallDate?: string | null;
}
export interface Computer {
  hostname: string;
  ip_addresses?: IPAddress[];
  physical_disks?: PhysicalDisk[];
  logical_disks?: LogicalDisk[];
  os_name?: string | null;
  os_version?: string | null;
  processors?: Processor[] | null;
  ram?: number | null;
  mac_addresses?: MACAddress[];
  motherboard?: string | null;
  last_boot?: string | null;
  is_virtual?: boolean | null;
  check_status?: CheckStatus | null;
  roles?: Role[];
  software?: Software[];
  video_cards?: VideoCard[];
  object_guid?: string | null;
  when_created?: string | null;
  when_changed?: string | null;
  enabled?: boolean | null;
  ad_notes?: string | null;
  local_notes?: string | null;
  is_deleted?: boolean | null;
  id: number;
  last_updated: string;
}
export interface Role {
  detected_on?: string | null;
  removed_on?: string | null;
  Name: string;
}
export interface ComputerBase {
  hostname: string;
  ip_addresses?: IPAddress[];
  physical_disks?: PhysicalDisk[];
  logical_disks?: LogicalDisk[];
  os_name?: string | null;
  os_version?: string | null;
  processors?: Processor[] | null;
  ram?: number | null;
  mac_addresses?: MACAddress[];
  motherboard?: string | null;
  last_boot?: string | null;
  is_virtual?: boolean | null;
  check_status?: CheckStatus | null;
  roles?: Role[];
  software?: Software[];
  video_cards?: VideoCard[];
  object_guid?: string | null;
  when_created?: string | null;
  when_changed?: string | null;
  enabled?: boolean | null;
  ad_notes?: string | null;
  local_notes?: string | null;
  is_deleted?: boolean | null;
}
export interface ComputerCreate {
  hostname: string;
  ip_addresses?: IPAddress[];
  physical_disks?: PhysicalDisk[];
  logical_disks?: LogicalDisk[];
  os_name?: string | null;
  os_version?: string | null;
  processors?: Processor[] | null;
  ram?: number | null;
  mac_addresses?: MACAddress[];
  motherboard?: string | null;
  last_boot?: string | null;
  is_virtual?: boolean | null;
  check_status?: CheckStatus | null;
  roles?: Role[];
  software?: Software[];
  video_cards?: VideoCard[];
  object_guid?: string | null;
  when_created?: string | null;
  when_changed?: string | null;
  enabled?: boolean | null;
  ad_notes?: string | null;
  local_notes?: string | null;
  is_deleted?: boolean | null;
}
export interface ComputerList {
  hostname: string;
  ip_addresses?: IPAddress[];
  physical_disks?: PhysicalDisk[];
  logical_disks?: LogicalDisk[];
  os_name?: string | null;
  os_version?: string | null;
  processors?: Processor[] | null;
  ram?: number | null;
  mac_addresses?: MACAddress[];
  motherboard?: string | null;
  last_boot?: string | null;
  is_virtual?: boolean | null;
  check_status?: CheckStatus | null;
  roles?: Role[];
  software?: Software[];
  video_cards?: VideoCard[];
  object_guid?: string | null;
  when_created?: string | null;
  when_changed?: string | null;
  enabled?: boolean | null;
  ad_notes?: string | null;
  local_notes?: string | null;
  is_deleted?: boolean | null;
  id: number;
  last_updated?: string | null;
}
export interface ComputerListItem {
  hostname: string;
  ip_addresses?: IPAddress[];
  physical_disks?: PhysicalDisk[];
  logical_disks?: LogicalDisk[];
  os_name?: string | null;
  os_version?: string | null;
  processors?: Processor[] | null;
  ram?: number | null;
  mac_addresses?: MACAddress[];
  motherboard?: string | null;
  last_boot?: string | null;
  is_virtual?: boolean | null;
  check_status?: CheckStatus | null;
  roles?: Role[];
  software?: Software[];
  video_cards?: VideoCard[];
  object_guid?: string | null;
  when_created?: string | null;
  when_changed?: string | null;
  enabled?: boolean | null;
  ad_notes?: string | null;
  local_notes?: string | null;
  is_deleted?: boolean | null;
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
  total_computers?: number | null;
  os_stats: OsStats;
  disk_stats: DiskStats;
  scan_stats: ScanStats;
  component_changes?: ComponentChangeStats[];
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
  id: number;
  hostname: string;
  disk_id: string;
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
  created_at: string;
  updated_at: string;
  scanned_hosts: number;
  successful_hosts: number;
  error?: string | null;
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
