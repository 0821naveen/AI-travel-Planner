import React from 'react';
import styles from './Checklist.module.css';

interface ChecklistItem {
  label: string;
  checked: boolean;
}

interface ChecklistProps {
  items: ChecklistItem[];
}

const Checklist: React.FC<ChecklistProps> = ({ items }) => (
  <ul className={styles.checklist}>
    {items.map((item, idx) => (
      <li key={idx} className={item.checked ? styles.checked : ''}>
        <input type="checkbox" checked={item.checked} readOnly /> {item.label}
      </li>
    ))}
  </ul>
);

export default Checklist;
