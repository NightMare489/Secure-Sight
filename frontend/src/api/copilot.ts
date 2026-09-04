import apiClient from './client';

export interface CopilotResult {
  answer: string;
  chart: { title: string; chart_type: 'bar' | 'line' | 'pie'; data: Array<{ bucket: string; incidents: number }> } | null;
  incidents: Array<{ id: string; event_type: string; timestamp: string; camera_name: string; zone_name: string; reviewed: boolean; has_clip: boolean; clip_url: string | null }>;
}

export interface CopilotHistoryMessage { role: 'user' | 'model'; text: string; }

export const copilotApi = {
  ask: async (message: string, history: CopilotHistoryMessage[]): Promise<CopilotResult> => (await apiClient.post('/copilot/chat', { message, history })).data,
};
