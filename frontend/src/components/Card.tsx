import React from 'react';
import styles from './Card.module.css';

type CardVariant = 'default' | 'insight' | 'caution' | 'review' | 'metric';

const Card: React.FC<{
  children: React.ReactNode;
  className?: string;
  variant?: CardVariant;
}> = ({ children, className, variant = 'default' }) => (
  <div className={`${styles.card} ${styles[variant]} ${className || ''}`}>{children}</div>
);

export default Card;
