import React from 'react';
import styles from './UtilityPanel.module.css';

const UtilityPanel: React.FC<{ children: React.ReactNode }> = ({ children }) => (
  <aside className={styles.utilityPanel}>{children}</aside>
);

export default UtilityPanel;
