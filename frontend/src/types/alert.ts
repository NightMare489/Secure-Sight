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
  event_type: 'ENTER' | 'EXIT' | 'PRESENT' | 'LOITERING' | 'OCCUPANCY_LIMIT';
  timestamp: string;
  snapshot_path: string | null;
  clip_path: string | null;
  zone_name: string;
  camera_name: string;
  acknowledged: boolean;
  acknowledged_at: string | null;
  acknowledgement_note: string | null;
}

export interface AlertFilter {
  camera_id?: string;
  zone_id?: string;
  event_type?: Alert['event_type'];
  start_time?: string;
  end_time?: string;
  page?: number;
  per_page?: number;
  acknowledged?: boolean;
}
