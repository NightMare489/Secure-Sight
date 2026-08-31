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
  created_at: string;
  updated_at: string;
}

export interface ZoneCreate {
  name: string;
  polygon_points: number[][];
  color?: string;
  alert_enabled?: boolean;
  is_active?: boolean;
}

export interface ZoneUpdate {
  name?: string;
  polygon_points?: number[][];
  color?: string;
  alert_enabled?: boolean;
  is_active?: boolean;
}
