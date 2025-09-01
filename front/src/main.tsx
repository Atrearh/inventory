import { ConfigProvider, theme } from 'antd';
import React, { useContext } from 'react';
import ReactDOM from 'react-dom/client';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { BrowserRouter } from 'react-router-dom';
import App from './App';
import ErrorBoundary from './components/ErrorBoundary';
import { AuthProvider } from './context/AuthContext';
import { TimezoneProvider } from './context/TimezoneContext';
import { ThemeContext, ThemeProvider } from './context/ThemeContext';
import './components/i18n';

// Кастомні стилі для скролу в темній темі
const globalStyles = (dark: boolean) => `
  body {
    margin: 0; 
  }
  body::-webkit-scrollbar {
    width: 8px;
  }
  body::-webkit-scrollbar-track {
    background: ${dark ? '#2c2c2c' : '#f1f1f1'};
  }
  body::-webkit-scrollbar-thumb {
    background: ${dark ? '#555' : '#888'};
    border-radius: 4px;
  }
  body::-webkit-scrollbar-thumb:hover {
    background: ${dark ? '#777' : '#555'};
  }
`;

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      retry: 1,
      staleTime: 5 * 60 * 1000, // 5 хвилин
      gcTime: 10 * 60 * 1000, // 10 хвилин
    },
  },
});

// Компонент для застосування теми
const AppWithTheme: React.FC = () => {
  const { dark } = useContext(ThemeContext);

  // Додаємо глобальні стилі для скролу
  React.useEffect(() => {
    const styleSheet = document.createElement('style');
    styleSheet.textContent = globalStyles(dark);
    document.head.appendChild(styleSheet);
    return () => {
      document.head.removeChild(styleSheet);
    };
  }, [dark]);

  return (
    <ConfigProvider
      theme={{
        algorithm: dark ? theme.darkAlgorithm : theme.defaultAlgorithm,
        token: {
          colorPrimary: '#1890ff',
          colorTextBase: dark ? '#d9d9d9' : '#000',
          colorBgBase: dark ? '#1a1a1a' : '#fff',
          colorBgContainer: dark ? '#2c2c2c' : '#fff',
          colorBorder: dark ? '#444' : '#d9d9d9',
        },
      }}
    >
      <App />
    </ConfigProvider>
  );
};

const Root = () => {
  return (
    <React.StrictMode>
      <ErrorBoundary>
        <AuthProvider>
          <TimezoneProvider>
            <ThemeProvider>
              <QueryClientProvider client={queryClient}>
                <BrowserRouter future={{ v7_startTransition: true, v7_relativeSplatPath: true }}>
                  <AppWithTheme />
                </BrowserRouter>
              </QueryClientProvider>
            </ThemeProvider>
          </TimezoneProvider>
        </AuthProvider>
      </ErrorBoundary>
    </React.StrictMode>
  );
};

ReactDOM.createRoot(document.getElementById('root')!).render(<Root />);