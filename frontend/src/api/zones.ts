/**
 * Zone API functions.
 */

import apiClient from './client';
import type { Zone, ZoneCreate, ZoneUpdate } from '../types/zone';

export const zonesApi = {
  getByCameraId: async (cameraId: string): Promise<Zone[]> => {
    const { data } = await apiClient.get(`/cameras/${cameraId}/zones`);
    return data.zones;
  },

  getById: async (id: string): Promise<Zone> => {
    const { data } = await apiClient.get(`/zones/${id}`);
    return data;
  },

  create: async (cameraId: string, zone: ZoneCreate): Promise<Zone> => {
    const { data } = await apiClient.post(`/cameras/${cameraId}/zones`, zone);
    return data;
  },

  update: async (id: string, zone: ZoneUpdate): Promise<Zone> => {
    const { data } = await apiClient.put(`/zones/${id}`, zone);
    return data;
  },

  delete: async (id: string): Promise<void> => {
    await apiClient.delete(`/zones/${id}`);
  },
};
