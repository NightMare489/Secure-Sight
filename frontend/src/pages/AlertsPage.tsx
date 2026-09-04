/** Alert queue with filtering, snapshots, and acknowledgement. */
import { useCallback, useEffect, useState } from 'react';
import { AlertTriangle, Check, Clock, Image, X } from 'lucide-react';
import toast from 'react-hot-toast';
import { alertsApi } from '../api/alerts';
import { useAlertStore } from '../store/alertStore';
import { useAlertSocket } from '../hooks/useWebSocket';
import { camerasApi } from '../api/cameras';
import type { Camera } from '../types/camera';
import type { Alert, AlertFilter } from '../types/alert';

const eventTypeColor: Record<Alert['event_type'], string> = {
  ENTER: 'badge-danger', EXIT: 'badge-success', PRESENT: 'badge-warning',
  LOITERING: 'badge-warning', OCCUPANCY_LIMIT: 'badge-danger',
};

export default function AlertsPage() {
  const { alerts, total, isLoading, fetchAlerts, addRealtimeAlert, replaceAlert } = useAlertStore();
  const [filters, setFilters] = useState<AlertFilter>({ per_page: 50, acknowledged: false });
  const [selected, setSelected] = useState<Alert | null>(null);
  const [note, setNote] = useState('');
  const [cameras, setCameras] = useState<Camera[]>([]);
  const loadAlerts = useCallback(() => fetchAlerts(filters), [fetchAlerts, filters]);
  useEffect(() => { loadAlerts(); }, [loadAlerts]);
  useEffect(() => { camerasApi.getAll().then(setCameras).catch(() => undefined); }, []);

  useAlertSocket(useCallback((data: any) => {
    if (data.event_type === 'PRESENT') return;
    addRealtimeAlert({ id: crypto.randomUUID(), zone_id: data.zone_id, camera_id: data.camera_id,
      tracker_id: data.tracker_id, global_person_id: data.global_person_id ?? null,
      association_confidence: data.association_confidence ?? null, association_method: data.association_method ?? null,
      event_type: data.event_type, timestamp: new Date(data.timestamp * 1000).toISOString(), snapshot_path: null, clip_path: null,
      zone_name: data.zone_name, camera_name: '', acknowledged: false, acknowledged_at: null, acknowledgement_note: null });
    loadAlerts();
  }, [addRealtimeAlert, loadAlerts]));

  const updateFilter = <K extends keyof AlertFilter>(key: K, value: AlertFilter[K]) => setFilters((current) => ({ ...current, page: 1, [key]: value }));
  const acknowledge = async (alert: Alert, acknowledged: boolean) => {
    try {
      const updated = await alertsApi.acknowledge(alert.id, acknowledged, note || undefined);
      replaceAlert(updated); setSelected(updated); setNote(updated.acknowledgement_note ?? '');
      toast.success(acknowledged ? 'Alert acknowledged' : 'Alert reopened'); loadAlerts();
    } catch { toast.error('Could not update alert'); }
  };

  return <div className="fade-in">
    <div className="page-header"><h1><AlertTriangle size={28} /> Alert Queue</h1></div>
    <div className="glass-card alert-filters">
      <select className="filter-control" value={filters.event_type ?? ''} onChange={(e) => updateFilter('event_type', (e.target.value || undefined) as AlertFilter['event_type'])}>
        <option value="">All event types</option><option value="ENTER">Entry</option><option value="EXIT">Exit</option><option value="LOITERING">Loitering</option><option value="OCCUPANCY_LIMIT">Occupancy limit</option>
      </select>
      <select className="filter-control" value={filters.acknowledged === undefined ? '' : String(filters.acknowledged)} onChange={(e) => updateFilter('acknowledged', e.target.value === '' ? undefined : e.target.value === 'true')}>
        <option value="false">Unacknowledged</option><option value="true">Acknowledged</option><option value="">All alerts</option>
      </select>
      <select className="filter-control" value={filters.camera_id ?? ''} onChange={(e) => updateFilter('camera_id', e.target.value || undefined)}><option value="">All cameras</option>{cameras.map((camera) => <option key={camera.id} value={camera.id}>{camera.name}</option>)}</select>
      <label className="filter-date"><span>From</span><input className="filter-control" type="datetime-local" aria-label="Start date" onChange={(e) => updateFilter('start_time', e.target.value || undefined)} /></label>
      <label className="filter-date"><span>To</span><input className="filter-control" type="datetime-local" aria-label="End date" onChange={(e) => updateFilter('end_time', e.target.value || undefined)} /></label>
      <span className="filter-summary">{total} matching alerts</span>
    </div>
    <div className="glass-card" style={{ overflow: 'hidden' }}>
      {!isLoading && alerts.length === 0 ? <div className="empty-state"><AlertTriangle size={48} /><p>No matching alerts.</p></div> : <table className="alerts-table"><thead><tr><th>Event</th><th>Camera / Zone</th><th>Person</th><th>Time</th><th>Status</th></tr></thead><tbody>{alerts.map((alert) => <tr key={alert.id} onClick={() => { setSelected(alert); setNote(alert.acknowledgement_note ?? ''); }} style={{ cursor: 'pointer' }}>
        <td><span className={`badge ${eventTypeColor[alert.event_type]}`}>{alert.event_type}</span></td><td>{alert.camera_name || 'Camera'}<br /><span style={{ color: 'var(--text-muted)' }}>{alert.zone_name || alert.zone_id.slice(0, 8)}</span></td>
        <td style={{ fontFamily: 'var(--font-mono)' }}>{alert.tracker_id ? (alert.global_person_id ? `G-${alert.global_person_id.slice(0, 8)}` : `#${alert.tracker_id}`) : 'Zone'}</td><td><Clock size={12} /> {new Date(alert.timestamp).toLocaleString()}</td>
        <td><span className={`badge ${alert.acknowledged ? 'badge-success' : 'badge-warning'}`}>{alert.acknowledged ? 'Acknowledged' : 'Open'}</span></td>
      </tr>)}</tbody></table>}
    </div>
    {selected && <div className="modal-overlay" onClick={() => setSelected(null)}><div className="modal-content" onClick={(e) => e.stopPropagation()}>
      <div className="modal-header"><h2>Alert details</h2><button className="btn btn-ghost btn-icon" onClick={() => setSelected(null)}><X size={18} /></button></div>
      {selected.clip_path ? <video controls preload="metadata" src={alertsApi.clipUrl(selected.id)} style={{ width: '100%', borderRadius: 8, marginBottom: 12 }} /> : selected.snapshot_path ? <img src={alertsApi.snapshotUrl(selected.id)} alt="Alert snapshot" style={{ width: '100%', borderRadius: 8, marginBottom: 12 }} /> : <p style={{ color: 'var(--text-muted)', marginBottom: 12 }}><Image size={16} /> No clip or snapshot is available for this event.</p>}
      <p><strong>{selected.event_type}</strong> — {selected.camera_name || 'Camera'} / {selected.zone_name}</p><p style={{ color: 'var(--text-secondary)', marginTop: 6 }}>{new Date(selected.timestamp).toLocaleString()}</p>
      <div className="form-group" style={{ marginTop: 14 }}><label>Operator note</label><textarea className="input" rows={3} value={note} onChange={(e) => setNote(e.target.value)} placeholder="Optional incident note" /></div>
      <div className="modal-actions"><button className="btn btn-secondary" onClick={() => setSelected(null)}>Close</button><button className={selected.acknowledged ? 'btn btn-secondary' : 'btn btn-primary'} onClick={() => acknowledge(selected, !selected.acknowledged)}><Check size={16} /> {selected.acknowledged ? 'Reopen' : 'Acknowledge'}</button></div>
    </div></div>}
  </div>;
}
