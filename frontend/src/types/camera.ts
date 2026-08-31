/**
 * Camera type definitions.
 */

export interface Camera {
  id: string;
  name: string;
  source_uri: string;
  source_type: 'file' | 'rtsp' | 'webcam';
  description: string;
  is_active: boolean;
  overlap_group: string | null;
  ground_plane_homography: number[][] | null;
  created_at: string;
  updated_at: string;
  zone_count: number;
  pipeline_status: PipelineStatus;
}

export type PipelineStatus = 'IDLE' | 'STARTING' | 'RUNNING' | 'STOPPING' | 'STOPPED' | 'ERROR';

export interface CameraCreate {
  name: string;
  source_uri: string;
  source_type: 'file' | 'rtsp' | 'webcam';
  description?: string;
  is_active?: boolean;
  overlap_group?: string | null;
  ground_plane_homography?: number[][] | null;
}

export interface CameraUpdate {
  name?: string;
  source_uri?: string;
  source_type?: 'file' | 'rtsp' | 'webcam';
  description?: string;
  is_active?: boolean;
  overlap_group?: string | null;
  ground_plane_homography?: number[][] | null;
}
