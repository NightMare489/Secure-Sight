/**
 * Alert Store — Zustand.
 *
 * Global state for alerts with real-time updates.
 */

import { create } from 'zustand';
import { alertsApi } from '../api/alerts';
import type { Alert } from '../types/alert';
import type { AlertFilter } from '../types/alert';

interface AlertState {
  alerts: Alert[];
  recentAlerts: Alert[];
  isLoading: boolean;
  error: string | null;
  total: number;

  // Actions
  fetchRecent: (limit?: number) => Promise<void>;
  fetchAlerts: (filters?: AlertFilter) => Promise<void>;
  replaceAlert: (alert: Alert) => void;
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

  fetchAlerts: async (filters) => {
    set({ isLoading: true, error: null });
    try {
      const { alerts, total } = await alertsApi.getAll(filters);
      set({ alerts, total, isLoading: false });
    } catch (err: any) {
      set({ error: err.response?.data?.error || 'Failed to fetch alerts', isLoading: false });
    }
  },

  addRealtimeAlert: (alert) => {
    set((state) => ({
      recentAlerts: [alert, ...state.recentAlerts].slice(0, 50),
    }));
  },

  replaceAlert: (alert) => set((state) => ({
    alerts: state.alerts.map((item) => item.id === alert.id ? alert : item),
    recentAlerts: state.recentAlerts.map((item) => item.id === alert.id ? alert : item),
  })),

  clearError: () => set({ error: null }),
}));
