/**
 * Alert API functions.
 */

import apiClient from './client';
import type { Alert, AlertFilter } from '../types/alert';

export const alertsApi = {
  getAll: async (filters?: AlertFilter): Promise<{ alerts: Alert[]; total: number }> => {
    const { data } = await apiClient.get('/alerts', { params: filters });
    return data;
  },

  getById: async (id: string): Promise<Alert> => {
    const { data } = await apiClient.get(`/alerts/${id}`);
    return data;
  },

  getRecent: async (limit = 20): Promise<Alert[]> => {
    const { data } = await apiClient.get('/alerts/recent', { params: { limit } });
    return data.alerts;
  },

  acknowledge: async (id: string, acknowledged: boolean, note?: string): Promise<Alert> => {
    const { data } = await apiClient.put(`/alerts/${id}/acknowledge`, { acknowledged, note });
    return data;
  },

  snapshotUrl: (id: string): string => `${apiClient.defaults.baseURL}/alerts/${id}/snapshot`,
  clipUrl: (id: string): string => `${apiClient.defaults.baseURL}/alerts/${id}/clip`,
};
