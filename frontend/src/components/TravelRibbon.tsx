import React from 'react';
import AccountBar from './AccountBar';
import brandMark from '../assets/atlas-brand-mark.svg';
import styles from './TravelRibbon.module.css';

const ribbonImages = [
  {
    title: 'Coastal Mornings',
    subtitle: 'Beach towns and slow arrivals',
    imageUrl: 'https://images.unsplash.com/photo-1507525428034-b723cf961d3e?auto=format&fit=crop&w=1200&q=80',
  },
  {
    title: 'City Energy',
    subtitle: 'Night markets and walkable streets',
    imageUrl: 'https://images.unsplash.com/photo-1467269204594-9661b134dd2b?auto=format&fit=crop&w=1200&q=80',
  },
  {
    title: 'Mountain Reset',
    subtitle: 'Quiet stays and scenic routes',
    imageUrl: 'https://images.unsplash.com/photo-1500530855697-b586d89ba3ee?auto=format&fit=crop&w=1200&q=80',
  },
  {
    title: 'Local Food Trails',
    subtitle: 'Cafes, markets, and signature dishes',
    imageUrl: 'https://images.unsplash.com/photo-1504674900247-0877df9cc836?auto=format&fit=crop&w=1200&q=80',
  },
  {
    title: 'Golden Hour Stops',
    subtitle: 'Photo moments worth building around',
    imageUrl: 'https://images.unsplash.com/photo-1501785888041-af3ef285b470?auto=format&fit=crop&w=1200&q=80',
  },
];

const loopImages = [...ribbonImages, ...ribbonImages];

const TravelRibbon: React.FC = () => (
  <section className={styles.ribbon} aria-label="Travel inspiration">
    <div className={styles.ribbonHeader}>
      <div className={styles.brandBlock}>
        <img src={brandMark} alt="Atlas logo" className={styles.logo} />
        <div>
          <div className={styles.eyebrow}>Atlas Travel Planner</div>
        </div>
      </div>
      <div className={styles.headerRight}>
        <AccountBar className={styles.accountBar} />
      </div>
    </div>
    <div className={styles.viewport}>
      <div className={styles.track}>
        {loopImages.map((item, index) => (
          <article
            key={`${item.title}-${index}`}
            className={styles.card}
            style={{ backgroundImage: `linear-gradient(180deg, rgba(10, 16, 26, 0.1), rgba(10, 16, 26, 0.62)), url(${item.imageUrl})` }}
          >
            <div className={styles.cardLabel}>{item.title}</div>
            <div className={styles.cardText}>{item.subtitle}</div>
          </article>
        ))}
      </div>
    </div>
  </section>
);

export default TravelRibbon;
