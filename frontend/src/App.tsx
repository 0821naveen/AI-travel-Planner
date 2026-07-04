import React from 'react';
import { BrowserRouter as Router, Routes, Route, Navigate, Outlet } from 'react-router-dom';
import AppLayout from './layouts/AppLayout';
import Dashboard from './app/dashboard/Dashboard';
import NewTrip from './app/new-trip/NewTrip';
import Clarification from './app/clarification/Clarification';
import Research from './app/research/Research';
import Itinerary from './app/itinerary/Itinerary';
import Budget from './app/budget/Budget';
import Review from './app/review/Review';
import Login from './app/login/Login';
import Signup from './app/login/Signup';
import { isAuthenticated } from './lib/planner';

const AppShell: React.FC = () => {
  return (
    <AppLayout>
      <Outlet />
    </AppLayout>
  );
};

const ProtectedRoutes: React.FC = () => {
  if (!isAuthenticated()) {
    return <Navigate to="/login" replace />;
  }
  return <AppShell />;
};

const App: React.FC = () => (
  <Router>
    <Routes>
      <Route path="/login" element={<Login />} />
      <Route path="/signup" element={<Signup />} />
      <Route element={<ProtectedRoutes />}>
        <Route path="/" element={<Navigate to="/dashboard" replace />} />
        <Route path="/dashboard" element={<Dashboard />} />
        <Route path="/new-trip" element={<NewTrip />} />
        <Route path="/clarification" element={<Clarification />} />
        <Route path="/research" element={<Research />} />
        <Route path="/itinerary" element={<Itinerary />} />
        <Route path="/budget" element={<Budget />} />
        <Route path="/review" element={<Review />} />
      </Route>
      <Route path="*" element={<Navigate to="/dashboard" replace />} />
    </Routes>
  </Router>
);

export default App;
