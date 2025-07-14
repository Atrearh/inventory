import React from 'react';
import ReactDOM from 'react-dom/client';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { BrowserRouter } from 'react-router-dom';
import App from './App';
import ErrorBoundary from './components/ErrorBoundary';
import { AuthProvider, useAuth } from './context/AuthContext';

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      retry: 1,
      enabled: false, // По умолчанию запросы отключены
    },
  },
});

const AppWithAuth: React.FC = () => {
  const { isAuthenticated } = useAuth();

  React.useEffect(() => {
    // Включаем запросы, только если пользователь аутентифицирован
    queryClient.setDefaultOptions({
      queries: {
        retry: 1,
        enabled: isAuthenticated,
      },
    });
  }, [isAuthenticated]);

  return (
    <BrowserRouter future={{ v7_startTransition: true, v7_relativeSplatPath: true }}>
      <App />
    </BrowserRouter>
  );
};

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <ErrorBoundary>
      <QueryClientProvider client={queryClient}>
        <AuthProvider>
          <AppWithAuth />
        </AuthProvider>
      </QueryClientProvider>
    </ErrorBoundary>
  </React.StrictMode>
);