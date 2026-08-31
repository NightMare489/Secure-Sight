/**
 * Camera Detail Page.
 *
 * Shows live camera feed, zone editor, zone list, and alerts.
 */

import { useEffect, useState, useCallback, useRef } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import {
  ArrowLeft, Play, Square, Plus, Trash2, Shield, AlertTriangle, Edit2, Eye, Pencil,
  Save, X,
} from 'lucide-react';
import { Stage, Layer, Line, Circle, Text as KonvaText } from 'react-konva';
import toast from 'react-hot-toast';
import { useCameraStore } from '../store/cameraStore';
import { useZoneStore } from '../store/zoneStore';
import { useStreamSocket } from '../hooks/useWebSocket';
import { API_BASE_URL } from '../api/client';
import type { ZoneCreate } from '../types/zone';
import { formatHomography, parseHomography } from '../utils/homography';

type EditorMode = 'view' | 'draw';

export default function CameraDetailPage() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const { selectedCamera, fetchCamera, startPipeline, stopPipeline, removeCamera, updateCamera } = useCameraStore();
  const { zones, fetchZones, addZone, removeZone } = useZoneStore();

  const [streamFrame, setStreamFrame] = useState<string | null>(null);
  const [editorMode, setEditorMode] = useState<EditorMode>('view');
  const [drawingPoints, setDrawingPoints] = useState<number[][]>([]);
  const [showAddZoneModal, setShowAddZoneModal] = useState(false);
  const [thumbnailError, setThumbnailError] = useState(false);
  const [editingIdentity, setEditingIdentity] = useState(false);
  const [overlapGroup, setOverlapGroup] = useState('');
  const [homography, setHomography] = useState('');
  const [identityError, setIdentityError] = useState<string | null>(null);

  const containerRef = useRef<HTMLDivElement>(null);
  const [containerSize, setContainerSize] = useState({ width: 800, height: 450 });

  // Fetch camera and zones
  useEffect(() => {
    if (id) {
      fetchCamera(id);
      fetchZones(id);
      setThumbnailError(false);
    }
  }, [id]);

  useEffect(() => {
    setOverlapGroup(selectedCamera?.overlap_group ?? '');
    setHomography(formatHomography(selectedCamera?.ground_plane_homography));
    setIdentityError(null);
  }, [selectedCamera?.id, selectedCamera?.overlap_group, selectedCamera?.ground_plane_homography]);

  // Container resize
  useEffect(() => {
    const updateSize = () => {
      if (containerRef.current) {
        const rect = containerRef.current.getBoundingClientRect();
        setContainerSize({ width: rect.width, height: rect.width * (9 / 16) });
      }
    };
    updateSize();
    window.addEventListener('resize', updateSize);
    return () => window.removeEventListener('resize', updateSize);
  }, []);

  // Stream socket
  const handleFrame = useCallback((data: any) => {
    if (data.frame) {
      setStreamFrame(`data:image/jpeg;base64,${data.frame}`);
    }
  }, []);

  useStreamSocket(id ?? null, handleFrame);

  const handleStageClick = (e: any) => {
    if (editorMode !== 'draw') return;

    const stage = e.target.getStage();
    const pointer = stage.getPointerPosition();
    if (!pointer) return;

    // Normalize to 0-1
    const normalizedX = pointer.x / containerSize.width;
    const normalizedY = pointer.y / containerSize.height;

    setDrawingPoints((prev) => [...prev, [normalizedX, normalizedY]]);
  };

  const finishDrawing = () => {
    if (drawingPoints.length < 3) {
      toast.error('Zone needs at least 3 points');
      return;
    }
    setShowAddZoneModal(true);
  };

  const cancelDrawing = () => {
    setDrawingPoints([]);
    setEditorMode('view');
  };

  const saveZone = async (name: string, color: string) => {
    if (!id) return;
    try {
      await addZone(id, {
        name,
        polygon_points: drawingPoints,
        color,
        alert_enabled: true,
        is_active: true,
      });
      toast.success(`Zone "${name}" created`);
      setDrawingPoints([]);
      setEditorMode('view');
      setShowAddZoneModal(false);
    } catch (err: any) {
      toast.error(err.response?.data?.error || 'Failed to create zone');
    }
  };

  const handleDeleteZone = async (zoneId: string) => {
    try {
      await removeZone(zoneId);
      toast.success('Zone deleted');
    } catch (err: any) {
      toast.error('Failed to delete zone');
    }
  };

  const handleDeleteCamera = async () => {
    if (!id || !selectedCamera) return;
    const confirm = window.confirm(`Are you sure you want to delete camera "${selectedCamera.name}"?`);
    if (!confirm) return;

    try {
      await removeCamera(id);
      toast.success('Camera deleted successfully');
      navigate('/');
    } catch (err) {
      toast.error('Failed to delete camera');
    }
  };

  const saveCrossCameraIdentity = async () => {
    if (!id) return;
    try {
      const groundPlaneHomography = parseHomography(homography);
      await updateCamera(id, {
        overlap_group: overlapGroup.trim() || null,
        ground_plane_homography: groundPlaneHomography,
      });
      setIdentityError(null);
      setEditingIdentity(false);
      toast.success(isRunning
        ? 'Cross-camera settings saved. Restart detection to apply them.'
        : 'Cross-camera settings saved.');
    } catch (error: any) {
      setIdentityError(error?.response?.data?.error || error?.message || 'Failed to save cross-camera settings');
    }
  };

  const isRunning = selectedCamera?.pipeline_status === 'RUNNING';

  return (
    <div className="fade-in">
      {/* Header */}
      <div className="page-header">
        <h1>
          <button className="btn btn-ghost btn-icon" onClick={() => navigate('/')}>
            <ArrowLeft size={20} />
          </button>
          {selectedCamera?.name || 'Camera'}
        </h1>
        <div style={{ display: 'flex', gap: 'var(--space-sm)' }}>
          <button
            className="btn btn-secondary"
            style={{ color: 'var(--text-muted)' }}
            onClick={handleDeleteCamera}
          >
            <Trash2 size={16} /> Delete Camera
          </button>
          {isRunning ? (
            <button
              className="btn btn-danger"
              onClick={async () => {
                try { await stopPipeline(id!); toast.success('Pipeline stopped'); } catch { toast.error('Failed to stop'); }
              }}
            >
              <Square size={16} /> Stop
            </button>
          ) : (
            <button
              className="btn btn-primary"
              onClick={async () => {
                try { await startPipeline(id!); toast.success('Pipeline started'); } catch (e: any) { toast.error(e.response?.data?.error || 'Failed to start'); }
              }}
            >
              <Play size={16} /> Start Detection
            </button>
          )}
        </div>
      </div>

      {/* Main Layout */}
      <div className="camera-detail-layout">
        {/* Stream + Zone Editor */}
        <div ref={containerRef} className="camera-stream-container glass-card" style={{ position: 'relative' }}>
          {streamFrame ? (
            <img
              src={streamFrame}
              alt="Camera stream"
              style={{ width: '100%', height: containerSize.height, objectFit: 'contain' }}
            />
          ) : !thumbnailError && id ? (
            <img
              src={`${API_BASE_URL}/api/v1/cameras/${id}/thumbnail`}
              alt="Camera preview"
              onError={() => setThumbnailError(true)}
              style={{ width: '100%', height: containerSize.height, objectFit: 'contain' }}
            />
          ) : (
            <div style={{
              width: '100%',
              height: containerSize.height,
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              color: 'var(--text-muted)',
              flexDirection: 'column',
              gap: '8px',
            }}>
              <Eye size={32} />
              <span>Start detection to view stream</span>
            </div>
          )}

          {/* Konva Zone Overlay */}
          <Stage
            width={containerSize.width}
            height={containerSize.height}
            style={{ position: 'absolute', top: 0, left: 0, cursor: editorMode === 'draw' ? 'crosshair' : 'default' }}
            onClick={handleStageClick}
          >
            <Layer>
              {/* Existing zones */}
              {zones.map((zone) => {
                const points = zone.polygon_points.flatMap(([x, y]) => [
                  x * containerSize.width,
                  y * containerSize.height,
                ]);
                return (
                  <Line
                    key={zone.id}
                    points={points}
                    closed
                    fill={zone.color + '33'}
                    stroke={zone.color}
                    strokeWidth={2}
                  />
                );
              })}

              {/* Zone labels */}
              {zones.map((zone) => {
                const x = zone.polygon_points[0][0] * containerSize.width;
                const y = zone.polygon_points[0][1] * containerSize.height - 20;
                return (
                  <KonvaText
                    key={`label-${zone.id}`}
                    x={x}
                    y={y}
                    text={zone.name}
                    fontSize={14}
                    fontStyle="bold"
                    fill={zone.color}
                  />
                );
              })}

              {/* Drawing points */}
              {drawingPoints.map(([x, y], i) => (
                <Circle
                  key={`draw-${i}`}
                  x={x * containerSize.width}
                  y={y * containerSize.height}
                  radius={5}
                  fill="#6366f1"
                  stroke="white"
                  strokeWidth={2}
                />
              ))}

              {/* Drawing lines */}
              {drawingPoints.length > 1 && (
                <Line
                  points={drawingPoints.flatMap(([x, y]) => [
                    x * containerSize.width,
                    y * containerSize.height,
                  ])}
                  closed={drawingPoints.length >= 3}
                  fill="#6366f122"
                  stroke="#6366f1"
                  strokeWidth={2}
                  dash={[5, 5]}
                />
              )}
            </Layer>
          </Stage>

          {/* Drawing toolbar */}
          {editorMode === 'draw' && (
            <div style={{
              position: 'absolute', bottom: 16, left: '50%', transform: 'translateX(-50%)',
              display: 'flex', gap: 8, padding: '8px 16px', background: 'var(--bg-overlay)',
              borderRadius: 'var(--radius-lg)', border: '1px solid var(--glass-border)',
            }}>
              <span style={{ color: 'var(--text-secondary)', fontSize: '0.85rem', display: 'flex', alignItems: 'center' }}>
                Click to add points ({drawingPoints.length})
              </span>
              <button className="btn btn-primary btn-sm" onClick={finishDrawing} disabled={drawingPoints.length < 3}>
                Finish
              </button>
              <button className="btn btn-secondary btn-sm" onClick={cancelDrawing}>Cancel</button>
            </div>
          )}
        </div>

        {/* Sidebar */}
        <div className="camera-sidebar">
          {/* Zone Management */}
          <div className="glass-card camera-sidebar-section">
            <h3>
              <Shield size={16} /> Zones
              <button
                className="btn btn-ghost btn-sm"
                style={{ marginLeft: 'auto' }}
                onClick={() => {
                  setEditorMode(editorMode === 'draw' ? 'view' : 'draw');
                  setDrawingPoints([]);
                }}
              >
                {editorMode === 'draw' ? <Eye size={14} /> : <Pencil size={14} />}
                {editorMode === 'draw' ? ' View' : ' Draw'}
              </button>
            </h3>

            {zones.length === 0 ? (
              <div style={{ color: 'var(--text-muted)', fontSize: '0.85rem', textAlign: 'center', padding: '16px' }}>
                No zones yet. Click "Draw" to create one.
              </div>
            ) : (
              zones.map((zone) => (
                <div key={zone.id} className="zone-item">
                  <div className="zone-item-info">
                    <div className="zone-color-dot" style={{ background: zone.color }} />
                    <span style={{ fontSize: '0.85rem' }}>{zone.name}</span>
                  </div>
                  <div className="zone-item-actions">
                    <button
                      className="btn btn-ghost btn-icon btn-sm"
                      onClick={() => handleDeleteZone(zone.id)}
                    >
                      <Trash2 size={14} />
                    </button>
                  </div>
                </div>
              ))
            )}
          </div>

          {/* Camera Info */}
          <div className="glass-card camera-sidebar-section">
            <h3>Camera Info</h3>
            <div style={{ fontSize: '0.85rem', color: 'var(--text-secondary)' }}>
              <p><strong>Type:</strong> {selectedCamera?.source_type}</p>
              <p style={{ marginTop: 4 }}><strong>URI:</strong> {selectedCamera?.source_uri}</p>
              <p style={{ marginTop: 4 }}><strong>Status:</strong>{' '}
                <span className={`badge ${isRunning ? 'badge-success' : 'badge-idle'}`}>
                  {selectedCamera?.pipeline_status || 'IDLE'}
                </span>
              </p>
            </div>
          </div>

          <div className="glass-card camera-sidebar-section">
            <h3>
              Cross-camera Identity
              <button
                className="btn btn-ghost btn-sm"
                style={{ marginLeft: 'auto' }}
                onClick={() => {
                  setEditingIdentity((editing) => !editing);
                  setIdentityError(null);
                }}
              >
                {editingIdentity ? <X size={14} /> : <Edit2 size={14} />}
                {editingIdentity ? ' Cancel' : ' Configure'}
              </button>
            </h3>

            {editingIdentity ? (
              <div>
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
                  <label>Ground-plane Homography (3×3 JSON)</label>
                  <textarea
                    className="input"
                    rows={6}
                    placeholder={'[[0.01, 0, -2.4],\n [0, 0.01, -1.1],\n [0, 0, 1]]'}
                    value={homography}
                    onChange={(e) => setHomography(e.target.value)}
                    spellCheck={false}
                    style={{ fontFamily: 'var(--font-mono)', resize: 'vertical' }}
                  />
                </div>
                <p style={{ color: 'var(--text-muted)', fontSize: '0.75rem', margin: '0 0 10px' }}>
                  Use the same group name and one calibrated matrix per overlapping camera. Leave both fields empty to disable matching for this camera.
                </p>
                {identityError && <p style={{ color: 'var(--danger)', fontSize: '0.8rem' }}>{identityError}</p>}
                <button className="btn btn-primary btn-sm" onClick={saveCrossCameraIdentity}>
                  <Save size={14} /> Save Settings
                </button>
              </div>
            ) : (
              <div style={{ fontSize: '0.85rem', color: 'var(--text-secondary)' }}>
                <p><strong>Group:</strong> {selectedCamera?.overlap_group || 'Not configured'}</p>
                <p style={{ marginTop: 4 }}>
                  <strong>Calibration:</strong>{' '}
                  {selectedCamera?.ground_plane_homography ? 'Configured' : 'Not configured'}
                </p>
              </div>
            )}
          </div>
        </div>
      </div>

      {/* Add Zone Name Modal */}
      {showAddZoneModal && (
        <AddZoneModal
          onClose={() => { setShowAddZoneModal(false); cancelDrawing(); }}
          onSubmit={saveZone}
        />
      )}
    </div>
  );
}

function AddZoneModal({
  onClose,
  onSubmit,
}: {
  onClose: () => void;
  onSubmit: (name: string, color: string) => void;
}) {
  const [name, setName] = useState('');
  const [color, setColor] = useState('#ef4444');

  const colors = ['#ef4444', '#f59e0b', '#22c55e', '#06b6d4', '#6366f1', '#ec4899'];

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal-content" onClick={(e) => e.stopPropagation()}>
        <div className="modal-header">
          <h2>Name Your Zone</h2>
          <button className="btn btn-ghost btn-icon" onClick={onClose}>✕</button>
        </div>

        <div className="form-group">
          <label>Zone Name</label>
          <input
            className="input"
            placeholder="e.g., Restricted Area"
            value={name}
            onChange={(e) => setName(e.target.value)}
            autoFocus
          />
        </div>

        <div className="form-group">
          <label>Color</label>
          <div style={{ display: 'flex', gap: 8 }}>
            {colors.map((c) => (
              <button
                key={c}
                onClick={() => setColor(c)}
                style={{
                  width: 32, height: 32, borderRadius: '50%', background: c,
                  border: color === c ? '3px solid white' : '3px solid transparent',
                  cursor: 'pointer', transition: 'all 150ms',
                }}
              />
            ))}
          </div>
        </div>

        <div className="modal-actions">
          <button className="btn btn-secondary" onClick={onClose}>Cancel</button>
          <button
            className="btn btn-primary"
            disabled={!name}
            onClick={() => onSubmit(name, color)}
          >
            <Plus size={16} /> Create Zone
          </button>
        </div>
      </div>
    </div>
  );
}
