import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';
import { BrowserRouter } from 'react-router-dom';
import './styles/tokens.css';
import './styles/app.css';
import './styles/recommend.css';
import './styles/recommend-loading.css';
import './styles/trace.css';
import './styles/completion.css';
import './styles/account.css';
import './styles/persona.css';
import './styles/reaction-preview.css';
import './styles/creator-seed.css';
import './styles/about.css';
import './styles/brand-logo.css';
import App from './App.tsx';

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <BrowserRouter>
      <App />
    </BrowserRouter>
  </StrictMode>,
);
