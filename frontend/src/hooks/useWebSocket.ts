/**
 * WebSocket Hook.
 *
 * Manages Socket.IO connections for camera streaming and alerts.
 */

import { useEffect, useRef, useCallback, useState } from 'react';
import { io, Socket } from 'socket.io-client';
import { API_BASE_URL } from '../api/client';

const SOCKET_URL = import.meta.env.VITE_SOCKET_URL || API_BASE_URL;

export function useStreamSocket(cameraId: string | null, onFrame?: (data: any) => void) {
  const socketRef = useRef<Socket | null>(null);

  useEffect(() => {
    if (!cameraId) return;

    const socket = io(`${SOCKET_URL}/stream`, {
      transports: ['websocket', 'polling'],
      reconnection: true,
      reconnectionDelay: 1000,
      autoConnect: false,
    });

    socketRef.current = socket;

    socket.on('connect', () => {
      console.log('[Stream] Connected');
      socket.emit('join_camera', { camera_id: cameraId });
    });

    // Socket.IO may reconnect without remounting the page. Joining again is
    // harmless and guarantees this detail view is back in the camera room.
    socket.io.on('reconnect', () => socket.emit('join_camera', { camera_id: cameraId }));

    socket.on('frame', (data: any) => {
      if (data.camera_id === cameraId && onFrame) {
        onFrame(data);
      }
    });

    socket.on('camera_status', (data: any) => {
      console.log('[Stream] Camera status:', data);
    });

    socket.on('disconnect', () => {
      console.log('[Stream] Disconnected');
    });

    socket.connect();

    return () => {
      socket.emit('leave_camera', { camera_id: cameraId });
      socket.disconnect();
      socketRef.current = null;
    };
  }, [cameraId, onFrame]);

  return socketRef;
}

/** Subscribe to several camera rooms through one socket for the dashboard wall. */
export function useCameraWall(cameraIds: string[]) {
  const [frames, setFrames] = useState<Record<string, { frame: string; detectionsCount: number }>>({});

  useEffect(() => {
    if (cameraIds.length === 0) return;
    const socket = io(`${SOCKET_URL}/stream`, { transports: ['websocket', 'polling'], reconnection: true, reconnectionDelay: 1000, autoConnect: false });
    socket.on('connect', () => cameraIds.forEach((cameraId) => socket.emit('join_camera', { camera_id: cameraId })));
    socket.on('frame', (data: any) => {
      if (data.frame) setFrames((current) => ({ ...current, [data.camera_id]: { frame: `data:image/jpeg;base64,${data.frame}`, detectionsCount: data.detections_count ?? 0 } }));
    });
    socket.connect();
    return () => { cameraIds.forEach((cameraId) => socket.emit('leave_camera', { camera_id: cameraId })); socket.disconnect(); };
  }, [cameraIds.join(',')]);

  return frames;
}

export function useAlertSocket(onAlert?: (data: any) => void) {
  const socketRef = useRef<Socket | null>(null);

  useEffect(() => {
    const socket = io(`${SOCKET_URL}/alerts`, {
      transports: ['websocket', 'polling'],
      reconnection: true,
      reconnectionDelay: 1000,
    });

    socketRef.current = socket;

    socket.on('connect', () => {
      console.log('[Alerts] Connected');
    });

    socket.on('zone_alert', (data: any) => {
      if (onAlert) {
        onAlert(data);
      }
    });

    socket.on('disconnect', () => {
      console.log('[Alerts] Disconnected');
    });

    return () => {
      socket.disconnect();
      socketRef.current = null;
    };
  }, [onAlert]);

  return socketRef;
}
