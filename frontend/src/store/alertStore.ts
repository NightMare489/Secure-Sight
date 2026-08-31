/**
 * Alert Store — Zustand.
 *
 * Global state for alerts with real-time updates.
 */

import { create } from 'zustand';
import { alertsApi } from '../api/alerts';
import type { Alert } from '../types/alert';

interface AlertState {
  alerts: Alert[];
  recentAlerts: Alert[];
  isLoading: boolean;
  error: string | null;
  total: number;

  // Actions
  fetchRecent: (limit?: number) => Promise<void>;
  addRealtimeAlert: (alert: Alert) => void;
  clearError: () => void;
}

export const useAlertStore = create<AlertState>((set) => ({
  alerts: [],
  recentAlerts: [],
  isLoading: false,
  error: null,
  total: 0,

  fetchRecent: async (limit = 20) => {
    set({ isLoading: true, error: null });
    try {
      const alerts = await alertsApi.getRecent(limit);
      set({ recentAlerts: alerts, isLoading: false });
    } catch (err: any) {
      set({ error: err.response?.data?.error || 'Failed to fetch alerts', isLoading: false });
    }
  },

  addRealtimeAlert: (alert) => {
    set((state) => ({
      recentAlerts: [alert, ...state.recentAlerts].slice(0, 50),
    }));
  },

  clearError: () => set({ error: null }),
}));
