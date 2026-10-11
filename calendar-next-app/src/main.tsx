// standard.css carries both axes: weight 400-700 and width 75%-100%.
import '@fontsource-variable/instrument-sans/standard.css';
import './styles/global.css';

import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';
import { App } from './app/App';
import { Providers } from './app/providers';

const host = document.getElementById('root');
if (!host) throw new Error('#root is missing from index.html');

createRoot(host).render(
  <StrictMode>
    <Providers>
      <App />
    </Providers>
  </StrictMode>,
);
