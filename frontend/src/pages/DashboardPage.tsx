/**
 * Dashboard Page.
 *
 * Main page showing camera grid, stats, and quick actions.
 */

import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Camera, Plus, Shield, AlertTriangle, Activity } from 'lucide-react';
import { useCameraStore } from '../store/cameraStore';
import { useAlertStore } from '../store/alertStore';
import { useAlertSocket, useCameraWall } from '../hooks/useWebSocket';
import toast from 'react-hot-toast';
import { API_BASE_URL } from '../api/client';
import type { CameraCreate } from '../types/camera';
import type { Camera as CameraType } from '../types/camera';
import { parseHomography } from '../utils/homography';

export default function DashboardPage() {
  const navigate = useNavigate();
  const { cameras, isLoading, fetchCameras, addCamera } = useCameraStore();
  const { recentAlerts, fetchRecent, addRealtimeAlert } = useAlertStore();
  const [showAddModal, setShowAddModal] = useState(false);
  const runningCameraIds = cameras.filter((camera) => camera.pipeline_status === 'RUNNING').map((camera) => camera.id);
  const liveFrames = useCameraWall(runningCameraIds);

  // Real-time alerts
  useAlertSocket((data) => {
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
      clip_path: null,
      zone_name: data.zone_name,
      camera_name: '',
      acknowledged: false,
      acknowledged_at: null,
      acknowledgement_note: null,
    });

    if (data.event_type === 'ENTER') {
      toast.error(`⚠️ Person entered "${data.zone_name}"`, {
        duration: 3000,
        style: { background: '#1a1a28', color: '#f1f5f9', border: '1px solid rgba(239,68,68,0.3)' },
      });
    }
  });

  useEffect(() => {
    fetchCameras();
    fetchRecent();
  }, []);

  const activePipelines = cameras.filter((c) => c.pipeline_status === 'RUNNING').length;
  const totalZones = cameras.reduce((sum, c) => sum + c.zone_count, 0);

  return (
    <div className="fade-in">
      <div className="page-header">
        <h1><Shield size={28} /> Dashboard</h1>
        <button className="btn btn-primary" onClick={() => setShowAddModal(true)}>
          <Plus size={16} /> Add Camera
        </button>
      </div>

      {/* Stats */}
      <div className="dashboard-stats">
        <div className="glass-card stat-card">
          <div className="stat-icon primary"><Camera size={22} /></div>
          <div className="stat-info">
            <h3>{cameras.length}</h3>
            <p>Total Cameras</p>
          </div>
        </div>
        <div className="glass-card stat-card">
          <div className="stat-icon success"><Activity size={22} /></div>
          <div className="stat-info">
            <h3>{activePipelines}</h3>
            <p>Active Pipelines</p>
          </div>
        </div>
        <div className="glass-card stat-card">
          <div className="stat-icon warning"><Shield size={22} /></div>
          <div className="stat-info">
            <h3>{totalZones}</h3>
            <p>Detection Zones</p>
          </div>
        </div>
        <div className="glass-card stat-card">
          <div className="stat-icon danger"><AlertTriangle size={22} /></div>
          <div className="stat-info">
            <h3>{recentAlerts.length}</h3>
            <p>Recent Alerts</p>
          </div>
        </div>
      </div>

      {/* Camera Grid */}
      {cameras.length === 0 && !isLoading ? (
        <div className="glass-card empty-state">
          <Camera size={48} />
          <p>No cameras configured yet</p>
          <button className="btn btn-primary" onClick={() => setShowAddModal(true)}>
            <Plus size={16} /> Add Your First Camera
          </button>
        </div>
      ) : (
        <div className="camera-grid">
          {cameras.map((camera) => (
            <CameraCard
              key={camera.id}
              camera={camera}
              liveFrame={liveFrames[camera.id]}
              onClick={() => navigate(`/cameras/${camera.id}`)}
            />
          ))}
        </div>
      )}

      {/* Add Camera Modal */}
      {showAddModal && (
        <AddCameraModal
          onClose={() => setShowAddModal(false)}
          onSubmit={async (data) => {
            try {
              await addCamera(data);
              toast.success('Camera added successfully');
              setShowAddModal(false);
            } catch (err: any) {
              toast.error(err.response?.data?.error || 'Failed to add camera');
            }
          }}
        />
      )}
    </div>
  );
}

function CameraCard({ camera, onClick, liveFrame }: { camera: CameraType; onClick: () => void; liveFrame?: { frame: string; detectionsCount: number } }) {
  const [hasError, setHasError] = useState(false);
  
  const statusBadge = {
    RUNNING: 'badge-success',
    ERROR: 'badge-danger',
    STARTING: 'badge-warning',
    STOPPING: 'badge-warning',
    IDLE: 'badge-idle',
    STOPPED: 'badge-idle',
  }[camera.pipeline_status] || 'badge-idle';

  const thumbnailUrl = `${API_BASE_URL}/api/v1/cameras/${camera.id}/thumbnail`;

  return (
    <div className="glass-card camera-card" onClick={onClick}>
      <div className="camera-card-preview">
        {liveFrame ? <img src={liveFrame.frame} alt={`${camera.name} live stream`} /> : !hasError ? (
          <img
            src={thumbnailUrl}
            alt={camera.name}
            onError={() => setHasError(true)}
            style={{ width: '100%', height: '100%', objectFit: 'cover' }}
          />
        ) : (
          <div className="placeholder">
            <Camera size={32} />
            <span style={{ fontSize: '0.8rem' }}>{camera.source_type.toUpperCase()}</span>
          </div>
        )}
        <div className="camera-card-status">
          <span className={`badge ${statusBadge}`}>{camera.pipeline_status}</span>
        </div>
      </div>
      <div className="camera-card-body">
        <h3>{camera.name}</h3>
        <p>{camera.description || camera.source_uri}</p>
        <div className="camera-card-footer">
          <span className="camera-card-zones">
            <Shield size={12} /> {camera.zone_count} zone{camera.zone_count !== 1 ? 's' : ''}
          </span>
          {liveFrame && <span className="camera-card-zones"><Activity size={12} /> {liveFrame.detectionsCount} people</span>}
        </div>
      </div>
    </div>
  );
}

function AddCameraModal({
  onClose,
  onSubmit,
}: {
  onClose: () => void;
  onSubmit: (data: CameraCreate) => void;
}) {
  const [name, setName] = useState('');
  const [sourceUri, setSourceUri] = useState('');
  const [sourceType, setSourceType] = useState<'file' | 'rtsp' | 'webcam'>('file');
  const [description, setDescription] = useState('');
  const [overlapGroup, setOverlapGroup] = useState('');
  const [homography, setHomography] = useState('');
  const [identityError, setIdentityError] = useState<string | null>(null);

  const handleSubmit = () => {
    try {
      const groundPlaneHomography = parseHomography(homography);
      setIdentityError(null);
      onSubmit({
        name,
        source_uri: sourceUri,
        source_type: sourceType,
        description,
        overlap_group: overlapGroup.trim() || null,
        ground_plane_homography: groundPlaneHomography,
      });
    } catch (error) {
      setIdentityError(error instanceof Error ? error.message : 'Invalid homography');
    }
  };

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal-content" onClick={(e) => e.stopPropagation()}>
        <div className="modal-header">
          <h2>Add Camera</h2>
          <button className="btn btn-ghost btn-icon" onClick={onClose}>✕</button>
        </div>

        <div className="form-group">
          <label>Camera Name</label>
          <input
            className="input"
            placeholder="e.g., Front Entrance"
            value={name}
            onChange={(e) => setName(e.target.value)}
          />
        </div>

        <div className="form-group">
          <label>Source Type</label>
          <select value={sourceType} onChange={(e) => setSourceType(e.target.value as any)}>
            <option value="file">Video File</option>
            <option value="rtsp">RTSP Stream</option>
            <option value="webcam">Webcam</option>
          </select>
        </div>

        <div className="form-group">
          <label>Source URI</label>
          <input
            className="input"
            placeholder={
              sourceType === 'file'
                ? 'path/to/video.mp4'
                : sourceType === 'rtsp'
                ? 'rtsp://user:pass@192.168.1.100/stream'
                : '0'
            }
            value={sourceUri}
            onChange={(e) => setSourceUri(e.target.value)}
          />
        </div>

        <div className="form-group">
          <label>Description (optional)</label>
          <input
            className="input"
            placeholder="e.g., Camera at the main entrance"
            value={description}
            onChange={(e) => setDescription(e.target.value)}
          />
        </div>

        <details style={{ marginTop: 8 }}>
          <summary style={{ cursor: 'pointer', color: 'var(--text-secondary)' }}>
            Cross-camera identity (optional)
          </summary>
          <p style={{ color: 'var(--text-muted)', fontSize: '0.8rem', margin: '8px 0' }}>
            Configure this only for cameras that see the same physical area.
          </p>
          <div className="form-group">
            <label>Overlap Group</label>
            <input
              className="input"
              placeholder="e.g., main-courtyard"
              value={overlapGroup}
              onChange={(e) => setOverlapGroup(e.target.value)}
            />
          </div>
          <div className="form-group">
            <label>Ground-plane Homography (3×3 JSON matrix)</label>
            <textarea
              className="input"
              rows={5}
              placeholder={'[[0.01, 0, -2.4],\n [0, 0.01, -1.1],\n [0, 0, 1]]'}
              value={homography}
              onChange={(e) => setHomography(e.target.value)}
              spellCheck={false}
              style={{ fontFamily: 'var(--font-mono)', resize: 'vertical' }}
            />
          </div>
          {identityError && <p style={{ color: 'var(--danger)', fontSize: '0.8rem' }}>{identityError}</p>}
        </details>

        <div className="modal-actions">
          <button className="btn btn-secondary" onClick={onClose}>Cancel</button>
          <button
            className="btn btn-primary"
            disabled={!name || !sourceUri}
            onClick={handleSubmit}
          >
            <Plus size={16} /> Add Camera
          </button>
        </div>
      </div>
    </div>
  );
}
