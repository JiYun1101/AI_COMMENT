import { Routes, Route, Navigate } from 'react-router-dom';
import { RecommendPage } from './pages/RecommendPage';
import { DashboardPage } from './pages/DashboardPage';
import { AccountHomePage } from './pages/AccountHomePage';
import { AccountPage } from './pages/AccountPage';
import { PersonaPage } from './pages/PersonaPage';

export default function App() {
  return (
    <Routes>
      <Route path="/" element={<RecommendPage />} />
      <Route path="/dashboard" element={<DashboardPage />} />
      <Route path="/account" element={<AccountHomePage />} />
      <Route path="/account/connect" element={<AccountPage />} />
      <Route path="/persona" element={<PersonaPage />} />
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}
