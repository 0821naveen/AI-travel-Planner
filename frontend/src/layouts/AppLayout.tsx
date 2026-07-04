import React, { useEffect, useState } from 'react';
import Sidebar from '../components/Sidebar';
import TravelRibbon from '../components/TravelRibbon';
import UtilityPanel from '../components/UtilityPanel';
import styles from './AppLayout.module.css';
import { clearAuthSession, fetchCurrentUser, isAuthenticated, loadAccessToken, saveAuthSession } from '../lib/planner';

interface AppLayoutProps {
  children: React.ReactNode;
  showUtilityPanel?: boolean;
  utilityPanelContent?: React.ReactNode;
}

const SIDEBAR_STATE_KEY = 'atlas_sidebar_collapsed';

const AppLayout: React.FC<AppLayoutProps> = ({ children, showUtilityPanel, utilityPanelContent }) => {
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false);

  useEffect(() => {
    setSidebarCollapsed(localStorage.getItem(SIDEBAR_STATE_KEY) === '1');
  }, []);

  useEffect(() => {
    if (!isAuthenticated()) {
      return;
    }
    fetchCurrentUser()
      .then((user) => {
        const token = loadAccessToken();
        if (!token) {
          return;
        }
        saveAuthSession({
          access_token: token,
          token_type: 'bearer',
          user,
        });
      })
      .catch(() => {
        clearAuthSession();
        window.location.href = '/login';
      });
  }, []);

  const toggleSidebar = () => {
    setSidebarCollapsed((previous) => {
      const next = !previous;
      localStorage.setItem(SIDEBAR_STATE_KEY, next ? '1' : '0');
      return next;
    });
  };

  return (
    <div className={`${styles.appLayout} ${sidebarCollapsed ? styles.collapsedLayout : ''}`}>
      <Sidebar collapsed={sidebarCollapsed} onToggle={toggleSidebar} />
      <div className={styles.mainArea}>
        <main className={styles.content}>
          <TravelRibbon />
          {children}
        </main>
      </div>
      {showUtilityPanel && <UtilityPanel>{utilityPanelContent}</UtilityPanel>}
    </div>
  );
};

export default AppLayout;
