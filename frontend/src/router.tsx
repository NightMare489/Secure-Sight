/**
 * Application Router.
 */

import { createBrowserRouter } from 'react-router-dom';
import App from './App';
import DashboardPage from './pages/DashboardPage';
import CameraDetailPage from './pages/CameraDetailPage';
import AlertsPage from './pages/AlertsPage';
import CopilotPage from './pages/CopilotPage';

export const router = createBrowserRouter([
  {
    path: '/',
    element: <App />,
    children: [
      { index: true, element: <DashboardPage /> },
      { path: 'cameras/:id', element: <CameraDetailPage /> },
      { path: 'alerts', element: <AlertsPage /> },
      { path: 'copilot', element: <CopilotPage /> },
    ],
  },
]);
