import React from 'react';
import brandMark from '../assets/atlas-brand-mark.svg';
import styles from './Header.module.css';

const Header: React.FC = () => (
  <header className={styles.header}>
    <div className={styles.left}>
      <img src={brandMark} alt="Atlas brand mark" className={styles.brandImage} />
      <div>
        <h1 className={styles.title}>Atlas Travel Planner</h1>
        <p className={styles.subtitle}>Multi-agent itinerary workspace</p>
      </div>
    </div>
    <div className={styles.right}>
      <span className={styles.statusDot} />
      System Healthy
    </div>
  </header>
);

export default Header;
