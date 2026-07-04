import React, { useState } from 'react';
import { Link, Navigate, useNavigate } from 'react-router-dom';
import styles from './Login.module.css';
import appStyles from '../AppPage.module.css';
import { isAuthenticated, loginUser, saveAuthSession } from '../../lib/planner';

const Login: React.FC = () => {
  const navigate = useNavigate();
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [submitting, setSubmitting] = useState(false);

  const isAuthed = isAuthenticated();
  if (isAuthed) {
    return <Navigate to="/dashboard" replace />;
  }

  const onSubmit = async (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();

    if (!email.trim() || !password.trim()) {
      setError('Enter email and password to continue.');
      return;
    }

    try {
      setSubmitting(true);
      const session = await loginUser({
        email: email.trim(),
        password,
      });
      saveAuthSession(session);
      navigate('/dashboard', { replace: true });
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Unable to sign in.');
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className={styles.authPage}>
      <div className={styles.card}>
        <div className={styles.brand}>
          <p className={styles.brandName}>Atlas Travel Planner</p>
          <p className={styles.brandTag}>Plan smarter trips with agent workflows</p>
        </div>
        <h1 className={styles.title}>Sign In</h1>
        <p className={styles.subtitle}>Access your travel planning workspace.</p>
        <form onSubmit={onSubmit} className={styles.form}>
          <label className={styles.field}>
            Email
            <input
              type="email"
              placeholder="you@company.com"
              value={email}
              onChange={(event) => {
                setEmail(event.target.value);
                setError('');
              }}
            />
          </label>
          <label className={styles.field}>
            Password
            <input
              type="password"
              placeholder="Enter password"
              value={password}
              onChange={(event) => {
                setPassword(event.target.value);
                setError('');
              }}
            />
          </label>
          {error ? <div className={appStyles.placeholder}>{error}</div> : null}
          <button type="submit" className={`${appStyles.primary} ${styles.action}`} disabled={submitting}>
            {submitting ? 'Signing In...' : 'Continue'}
          </button>
        </form>
        <div className={styles.hint}>Use your registered account credentials to continue.</div>
        <div className={styles.switch}>New here? <Link to="/signup">Create an account</Link></div>
      </div>
    </div>
  );
};

export default Login;
