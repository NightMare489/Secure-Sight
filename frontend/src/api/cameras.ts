/**
 * Camera API functions.
 */

import apiClient from './client';
import type { Camera, CameraCreate, CameraUpdate } from '../types/camera';

export const camerasApi = {
  getAll: async (): Promise<Camera[]> => {
    const { data } = await apiClient.get('/cameras');
    return data.cameras;
  },

  getById: async (id: string): Promise<Camera> => {
    const { data } = await apiClient.get(`/cameras/${id}`);
    return data;
  },

  create: async (camera: CameraCreate): Promise<Camera> => {
    const { data } = await apiClient.post('/cameras', camera);
    return data;
  },

  update: async (id: string, camera: CameraUpdate): Promise<Camera> => {
    const { data } = await apiClient.put(`/cameras/${id}`, camera);
    return data;
  },

  delete: async (id: string): Promise<void> => {
    await apiClient.delete(`/cameras/${id}`);
  },

  startPipeline: async (id: string): Promise<void> => {
    await apiClient.post(`/cameras/${id}/start`);
  },

  stopPipeline: async (id: string): Promise<void> => {
    await apiClient.post(`/cameras/${id}/stop`);
  },
};
