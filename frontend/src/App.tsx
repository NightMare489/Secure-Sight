/**
 * Root Application Layout.
 *
 * Provides the sidebar navigation and main content area.
 */

import { Outlet, NavLink } from 'react-router-dom';
import { Toaster } from 'react-hot-toast';
import { LayoutDashboard, AlertTriangle, Shield, Bot } from 'lucide-react';
import './index.css';
import './styles/dashboard.css';

function App() {
  return (
    <div className="app-layout">
      <Toaster position="top-right" />

      {/* Sidebar */}
      <aside className="sidebar">
        <div className="sidebar-logo">
          <Shield size={24} />
          Secure Sight
        </div>

        <nav className="sidebar-nav">
          <NavLink to="/" end className={({ isActive }) => `nav-link ${isActive ? 'active' : ''}`}>
            <LayoutDashboard size={18} />
            Dashboard
          </NavLink>
          <NavLink to="/alerts" className={({ isActive }) => `nav-link ${isActive ? 'active' : ''}`}>
            <AlertTriangle size={18} />
            Alerts
          </NavLink>
          <NavLink to="/copilot" className={({ isActive }) => `nav-link ${isActive ? 'active' : ''}`}>
            <Bot size={18} />
            Analytics Copilot
          </NavLink>
        </nav>

        <div style={{ marginTop: 'auto', fontSize: '0.75rem', color: 'var(--text-muted)', textAlign: 'center' }}>
          Secure Sight v0.1.0
        </div>
      </aside>

      {/* Main Content */}
      <main className="main-content">
        <Outlet />
      </main>
    </div>
  );
}

export default App;
