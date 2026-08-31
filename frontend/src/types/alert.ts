/**
 * Alert type definitions.
 */

export interface Alert {
  id: string;
  zone_id: string;
  camera_id: string;
  tracker_id: number;
  global_person_id: string | null;
  association_confidence: number | null;
  association_method: string | null;
  event_type: 'ENTER' | 'EXIT' | 'PRESENT';
  timestamp: string;
  snapshot_path: string | null;
  zone_name: string;
  camera_name: string;
}

export interface AlertFilter {
  camera_id?: string;
  zone_id?: string;
  event_type?: 'ENTER' | 'EXIT' | 'PRESENT';
  start_time?: string;
  end_time?: string;
  page?: number;
  per_page?: number;
}
