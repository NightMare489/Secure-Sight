/**
 * Zone Store — Zustand.
 *
 * Global state for zones with CRUD operations.
 */

import { create } from 'zustand';
import { zonesApi } from '../api/zones';
import type { Zone, ZoneCreate, ZoneUpdate } from '../types/zone';

interface ZoneState {
  zones: Zone[];
  isLoading: boolean;
  error: string | null;

  // Actions
  fetchZones: (cameraId: string) => Promise<void>;
  addZone: (cameraId: string, data: ZoneCreate) => Promise<Zone>;
  updateZone: (id: string, data: ZoneUpdate) => Promise<void>;
  removeZone: (id: string) => Promise<void>;
  clearZones: () => void;
  clearError: () => void;
}

export const useZoneStore = create<ZoneState>((set) => ({
  zones: [],
  isLoading: false,
  error: null,

  fetchZones: async (cameraId) => {
    set({ isLoading: true, error: null });
    try {
      const zones = await zonesApi.getByCameraId(cameraId);
      set({ zones, isLoading: false });
    } catch (err: any) {
      set({ error: err.response?.data?.error || 'Failed to fetch zones', isLoading: false });
    }
  },

  addZone: async (cameraId, data) => {
    const zone = await zonesApi.create(cameraId, data);
    set((state) => ({ zones: [...state.zones, zone] }));
    return zone;
  },

  updateZone: async (id, data) => {
    const updated = await zonesApi.update(id, data);
    set((state) => ({
      zones: state.zones.map((z) => (z.id === id ? updated : z)),
    }));
  },

  removeZone: async (id) => {
    await zonesApi.delete(id);
    set((state) => ({
      zones: state.zones.filter((z) => z.id !== id),
    }));
  },

  clearZones: () => set({ zones: [] }),
  clearError: () => set({ error: null }),
}));
