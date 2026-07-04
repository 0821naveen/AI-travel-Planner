import React from 'react';
import styles from './AccountCard.module.css';
import { clearAuthSession, loadCurrentUser } from '../lib/planner';

const AccountCard: React.FC = () => {
  const user = loadCurrentUser();

  if (!user) {
    return null;
  }

  const onLogout = () => {
    clearAuthSession();
    window.location.href = '/login';
  };

  return (
    <aside className={styles.shell}>
      <div className={styles.card}>
        <div className={styles.label}>Account</div>
        <div className={styles.email}>{user.email}</div>
        <div className={styles.metaRow}>
          <span className={styles.badge}>{user.is_superuser ? 'Superuser' : user.role}</span>
          <span className={styles.meta}>Signed in</span>
        </div>
        <button type="button" className={styles.logoutButton} onClick={onLogout}>
          Sign Out
        </button>
      </div>
    </aside>
  );
};

export default AccountCard;
