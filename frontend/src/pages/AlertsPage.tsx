/**
 * Alerts Page.
 *
 * Displays alert history with filtering.
 */

import { useEffect, useState, useCallback } from 'react';
import { AlertTriangle, Clock } from 'lucide-react';
import { useAlertStore } from '../store/alertStore';
import { useAlertSocket } from '../hooks/useWebSocket';

export default function AlertsPage() {
  const { recentAlerts, fetchRecent, addRealtimeAlert } = useAlertStore();

  useAlertSocket(
    useCallback((data: any) => {
      addRealtimeAlert({
        id: crypto.randomUUID(),
        zone_id: data.zone_id,
        camera_id: data.camera_id,
        tracker_id: data.tracker_id,
        global_person_id: data.global_person_id ?? null,
        association_confidence: data.association_confidence ?? null,
        association_method: data.association_method ?? null,
        event_type: data.event_type,
        timestamp: new Date(data.timestamp * 1000).toISOString(),
        snapshot_path: null,
        zone_name: data.zone_name,
        camera_name: '',
      });
    }, [])
  );

  useEffect(() => {
    fetchRecent(50);
  }, []);

  const formatTime = (ts: string) => {
    const d = new Date(ts);
    return d.toLocaleString();
  };

  const eventTypeColor = {
    ENTER: 'badge-danger',
    EXIT: 'badge-success',
    PRESENT: 'badge-warning',
  };

  return (
    <div className="fade-in">
      <div className="page-header">
        <h1><AlertTriangle size={28} /> Alerts</h1>
      </div>

      <div className="glass-card" style={{ overflow: 'hidden' }}>
        {recentAlerts.length === 0 ? (
          <div className="empty-state">
            <AlertTriangle size={48} />
            <p>No alerts yet. Start a detection pipeline to begin monitoring.</p>
          </div>
        ) : (
          <table className="alerts-table">
            <thead>
              <tr>
                <th>Event</th>
                <th>Zone</th>
                <th>Person ID</th>
                <th>Time</th>
              </tr>
            </thead>
            <tbody>
              {recentAlerts.map((alert) => (
                <tr key={alert.id}>
                  <td>
                    <span className={`badge ${eventTypeColor[alert.event_type]}`}>
                      {alert.event_type}
                    </span>
                  </td>
                  <td>{alert.zone_name || alert.zone_id.slice(0, 8)}</td>
                  <td style={{ fontFamily: 'var(--font-mono)' }}>
                    {alert.global_person_id
                      ? `G-${alert.global_person_id.slice(0, 8)}`
                      : `#${alert.tracker_id}`}
                  </td>
                  <td style={{ display: 'flex', alignItems: 'center', gap: 4, color: 'var(--text-secondary)' }}>
                    <Clock size={12} />
                    {formatTime(alert.timestamp)}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
}
