import React from 'react';
import { NavLink } from 'react-router-dom';
import styles from './Sidebar.module.css';

type SidebarProps = {
  collapsed: boolean;
  onToggle: () => void;
};

type NavItem = {
  label: string;
  to: string;
  section: 'main' | 'workspace' | 'settings';
  icon: React.ReactNode;
};

const navItems: NavItem[] = [
  {
    label: 'Dashboard',
    to: '/dashboard',
    section: 'main',
    icon: (
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
        <path d="M3 11.5 12 4l9 7.5" />
        <path d="M5.5 10.5V20h13V10.5" />
        <path d="M9.5 20v-5h5v5" />
      </svg>
    ),
  },
  {
    label: 'New Trip',
    to: '/new-trip',
    section: 'main',
    icon: (
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
        <path d="M12 5v14" />
        <path d="M5 12h14" />
      </svg>
    ),
  },
  {
    label: 'Clarification',
    to: '/clarification',
    section: 'workspace',
    icon: (
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
        <path d="M7 10h10" />
        <path d="M7 14h6" />
        <path d="M6 4h12a2 2 0 0 1 2 2v8a2 2 0 0 1-2 2h-5l-4 4v-4H6a2 2 0 0 1-2-2V6a2 2 0 0 1 2-2Z" />
      </svg>
    ),
  },
  {
    label: 'Research',
    to: '/research',
    section: 'workspace',
    icon: (
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
        <circle cx="11" cy="11" r="6" />
        <path d="m20 20-4.2-4.2" />
      </svg>
    ),
  },
  {
    label: 'Itinerary',
    to: '/itinerary',
    section: 'workspace',
    icon: (
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
        <rect x="4" y="5" width="16" height="15" rx="2" />
        <path d="M8 3v4" />
        <path d="M16 3v4" />
        <path d="M4 10h16" />
      </svg>
    ),
  },
  {
    label: 'Budget',
    to: '/budget',
    section: 'workspace',
    icon: (
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
        <path d="M6 18V9" />
        <path d="M12 18V5" />
        <path d="M18 18v-7" />
      </svg>
    ),
  },
  {
    label: 'Review & Export',
    to: '/review',
    section: 'settings',
    icon: (
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
        <path d="M8 7V5.5A2.5 2.5 0 0 1 10.5 3h7A2.5 2.5 0 0 1 20 5.5v13a2.5 2.5 0 0 1-2.5 2.5h-7A2.5 2.5 0 0 1 8 18.5V17" />
        <path d="M4 12h11" />
        <path d="m11 8 4 4-4 4" />
      </svg>
    ),
  },
];

const Sidebar: React.FC<SidebarProps> = ({ collapsed, onToggle }) => {
  const renderSection = (section: NavItem['section'], title: string) => {
    const items = navItems.filter((item) => item.section === section);
    return (
      <div className={styles.navSection}>
        {!collapsed ? <div className={styles.sectionLabel}>{title}</div> : null}
        <ul className={styles.navList}>
          {items.map((item) => (
            <li key={item.to}>
              <NavLink
                reloadDocument
                to={item.to}
                title={item.label}
                className={({ isActive }) => `${styles.navLink} ${isActive ? styles.active : ''}`}
              >
                <span className={styles.navIcon}>{item.icon}</span>
                <span className={styles.navText}>{item.label}</span>
              </NavLink>
            </li>
          ))}
        </ul>
      </div>
    );
  };

  return (
    <aside className={`${styles.sidebar} ${collapsed ? styles.collapsed : ''}`}>
      <div className={styles.panel}>
        <div className={styles.topRow}>
          <button
            type="button"
            className={styles.toggle}
            onClick={onToggle}
            aria-label={collapsed ? 'Expand sidebar' : 'Collapse sidebar'}
            title={collapsed ? 'Expand sidebar' : 'Collapse sidebar'}
          >
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
              {collapsed ? <path d="m9 18 6-6-6-6" /> : <path d="m15 18-6-6 6-6" />}
            </svg>
          </button>
        </div>
        <nav className={styles.nav}>
          {renderSection('main', 'Main')}
          {renderSection('workspace', 'Workspace')}
          {renderSection('settings', 'Export')}
        </nav>
      </div>
    </aside>
  );
};

export default Sidebar;
