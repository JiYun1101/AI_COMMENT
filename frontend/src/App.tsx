import { Routes, Route, Navigate } from 'react-router-dom';
import { RecommendPage } from './pages/RecommendPage';
import { DashboardPage } from './pages/DashboardPage';
import { AccountHomePage } from './pages/AccountHomePage';
import { AccountPage } from './pages/AccountPage';
import { PersonaPage } from './pages/PersonaPage';
import { ReactionPreviewPage } from './pages/ReactionPreviewPage';
import { CreatorSeedPage } from './pages/CreatorSeedPage';
import { AboutPage } from './pages/AboutPage';

export default function App() {
  return (
    <Routes>
      <Route path="/" element={<RecommendPage />} />
      <Route path="/about" element={<AboutPage />} />
      <Route path="/reaction-preview" element={<ReactionPreviewPage />} />
      <Route path="/creator-comment" element={<CreatorSeedPage />} />
      <Route path="/dashboard" element={<DashboardPage />} />
      <Route path="/account" element={<AccountHomePage />} />
      <Route path="/account/connect" element={<AccountPage />} />
      <Route path="/persona" element={<PersonaPage />} />
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}
