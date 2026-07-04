import React from 'react';
import styles from './FilterBar.module.css';

const FilterBar: React.FC<{ children?: React.ReactNode }> = ({ children }) => (
  <div className={styles.filterBar}>{children}</div>
);

export default FilterBar;
