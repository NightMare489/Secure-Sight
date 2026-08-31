/**
 * Camera Store — Zustand.
 *
 * Global state for cameras with CRUD operations and pipeline control.
 */

import { create } from 'zustand';
import { camerasApi } from '../api/cameras';
import type { Camera, CameraCreate, CameraUpdate } from '../types/camera';

interface CameraState {
  cameras: Camera[];
  selectedCamera: Camera | null;
  isLoading: boolean;
  error: string | null;

  // Actions
  fetchCameras: () => Promise<void>;
  fetchCamera: (id: string) => Promise<void>;
  addCamera: (data: CameraCreate) => Promise<Camera>;
  updateCamera: (id: string, data: CameraUpdate) => Promise<void>;
  removeCamera: (id: string) => Promise<void>;
  startPipeline: (id: string) => Promise<void>;
  stopPipeline: (id: string) => Promise<void>;
  setSelectedCamera: (camera: Camera | null) => void;
  updateCameraStatus: (id: string, status: string) => void;
  clearError: () => void;
}

export const useCameraStore = create<CameraState>((set, get) => ({
  cameras: [],
  selectedCamera: null,
  isLoading: false,
  error: null,

  fetchCameras: async () => {
    set({ isLoading: true, error: null });
    try {
      const cameras = await camerasApi.getAll();
      set({ cameras, isLoading: false });
    } catch (err: any) {
      set({ error: err.response?.data?.error || 'Failed to fetch cameras', isLoading: false });
    }
  },

  fetchCamera: async (id) => {
    set({ isLoading: true, error: null });
    try {
      const camera = await camerasApi.getById(id);
      set({ selectedCamera: camera, isLoading: false });
    } catch (err: any) {
      set({ error: err.response?.data?.error || 'Failed to fetch camera', isLoading: false });
    }
  },

  addCamera: async (data) => {
    const camera = await camerasApi.create(data);
    set((state) => ({ cameras: [camera, ...state.cameras] }));
    return camera;
  },

  updateCamera: async (id, data) => {
    const updated = await camerasApi.update(id, data);
    set((state) => ({
      cameras: state.cameras.map((c) => (c.id === id ? updated : c)),
      selectedCamera: state.selectedCamera?.id === id ? updated : state.selectedCamera,
    }));
  },

  removeCamera: async (id) => {
    await camerasApi.delete(id);
    set((state) => ({
      cameras: state.cameras.filter((c) => c.id !== id),
      selectedCamera: state.selectedCamera?.id === id ? null : state.selectedCamera,
    }));
  },

  startPipeline: async (id) => {
    await camerasApi.startPipeline(id);
    get().updateCameraStatus(id, 'RUNNING');
  },

  stopPipeline: async (id) => {
    await camerasApi.stopPipeline(id);
    get().updateCameraStatus(id, 'STOPPED');
  },

  setSelectedCamera: (camera) => set({ selectedCamera: camera }),

  updateCameraStatus: (id, status) => {
    set((state) => ({
      cameras: state.cameras.map((c) =>
        c.id === id ? { ...c, pipeline_status: status as Camera['pipeline_status'] } : c
      ),
      selectedCamera:
        state.selectedCamera?.id === id
          ? { ...state.selectedCamera, pipeline_status: status as Camera['pipeline_status'] }
          : state.selectedCamera,
    }));
  },

  clearError: () => set({ error: null }),
}));
