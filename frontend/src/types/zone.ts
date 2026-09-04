/**
 * Zone type definitions.
 */

export interface Zone {
  id: string;
  camera_id: string;
  name: string;
  polygon_points: number[][];
  color: string;
  alert_enabled: boolean;
  is_active: boolean;
  rule_type: 'intrusion' | 'loitering' | 'occupancy_limit';
  dwell_threshold_seconds: number | null;
  occupancy_limit: number | null;
  alert_cooldown_seconds: number;
  created_at: string;
  updated_at: string;
}

export interface ZoneCreate {
  name: string;
  polygon_points: number[][];
  color?: string;
  alert_enabled?: boolean;
  is_active?: boolean;
  rule_type?: 'intrusion' | 'loitering' | 'occupancy_limit';
  dwell_threshold_seconds?: number | null;
  occupancy_limit?: number | null;
  alert_cooldown_seconds?: number;
}

export interface ZoneUpdate {
  name?: string;
  polygon_points?: number[][];
  color?: string;
  alert_enabled?: boolean;
  is_active?: boolean;
  rule_type?: 'intrusion' | 'loitering' | 'occupancy_limit';
  dwell_threshold_seconds?: number | null;
  occupancy_limit?: number | null;
  alert_cooldown_seconds?: number;
}
