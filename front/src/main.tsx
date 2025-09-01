import { ConfigProvider, theme, Button } from 'antd';
import React, { useState } from 'react';
import ReactDOM from 'react-dom/client';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { BrowserRouter } from 'react-router-dom';
import App from './App';
import ErrorBoundary from './components/ErrorBoundary';
import { AuthProvider } from './context/AuthContext';
import { TimezoneProvider } from './context/TimezoneContext';
import './components/i18n';

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      retry: 1,
      staleTime: 5 * 60 * 1000, // 5 хвилин
      gcTime: 10 * 60 * 1000, // 10 хвилин
    },
  },
});

const Root = () => {
  const [dark, setDark] = useState(false);

  return (
    <React.StrictMode>
      <ErrorBoundary>
        <AuthProvider>
          <TimezoneProvider>
            <QueryClientProvider client={queryClient}>
              <BrowserRouter future={{ v7_startTransition: true, v7_relativeSplatPath: true }}>
                <ConfigProvider
                  theme={{
                    algorithm: dark ? theme.darkAlgorithm : theme.defaultAlgorithm,
                    token: { colorPrimary: '#1890ff' },
                  }}
                >
                  <div style={{ position: 'fixed', bottom: 16, right: 16, zIndex: 999 }}>
                    <Button onClick={() => setDark(!dark)}>{dark ? 'Light' : 'Dark'} Theme</Button>
                  </div>
                  <App />
                </ConfigProvider>
              </BrowserRouter>
            </QueryClientProvider>
          </TimezoneProvider>
        </AuthProvider>
      </ErrorBoundary>
    </React.StrictMode>
  );
};

ReactDOM.createRoot(document.getElementById('root')!).render(<Root />);