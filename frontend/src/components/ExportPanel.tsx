import React from 'react';
import styles from './ExportPanel.module.css';

const ExportPanel: React.FC<{ children?: React.ReactNode }> = ({ children }) => (
  <div className={styles.exportPanel}>{children}</div>
);

export default ExportPanel;
