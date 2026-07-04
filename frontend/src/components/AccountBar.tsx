import React, { useEffect, useRef, useState } from 'react';
import styles from './AccountBar.module.css';
import { clearAuthSession, loadCurrentUser } from '../lib/planner';

type AccountBarProps = {
  className?: string;
};

const AccountBar: React.FC<AccountBarProps> = ({ className }) => {
  const user = loadCurrentUser();
  const [open, setOpen] = useState(false);
  const rootRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    const handlePointerDown = (event: MouseEvent) => {
      if (!rootRef.current) {
        return;
      }
      if (!rootRef.current.contains(event.target as Node)) {
        setOpen(false);
      }
    };

    document.addEventListener('mousedown', handlePointerDown);
    return () => document.removeEventListener('mousedown', handlePointerDown);
  }, []);

  if (!user) {
    return null;
  }

  const onLogout = () => {
    clearAuthSession();
    window.location.href = '/login';
  };

  const accountLabel = user.full_name || user.email || 'Account';

  return (
    <div ref={rootRef} className={`${styles.bar} ${className || ''}`}>
      <button
        type="button"
        className={styles.accountButton}
        onClick={() => setOpen((value) => !value)}
        aria-haspopup="menu"
        aria-expanded={open}
      >
        <span className={styles.accountText}>My Account</span>
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
          <path d={open ? 'm18 15-6-6-6 6' : 'm6 9 6 6 6-6'} />
        </svg>
      </button>
      {open ? (
        <div className={styles.dropdown} role="menu">
          <div className={styles.dropdownLabel}>{accountLabel}</div>
          <button type="button" className={styles.dropdownAction} onClick={onLogout} role="menuitem">
            Sign Out
          </button>
        </div>
      ) : null}
    </div>
  );
};

export default AccountBar;
