import React from 'react';
import styles from './StatusBadge.module.css';

interface StatusBadgeProps {
  status: 'active' | 'awaiting' | 'review' | 'exported' | 'complete' | 'skipped' | 'waiting';
}

const StatusBadge: React.FC<StatusBadgeProps> = ({ status }) => (
  <span className={`${styles.badge} ${styles[status]}`}>{status}</span>
);

export default StatusBadge;
