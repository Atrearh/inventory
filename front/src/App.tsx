import { Routes, Route, Navigate } from 'react-router-dom';
import { Suspense, lazy } from 'react';
import { useAuth } from './context/AuthContext';
import { ThemeProvider } from './context/ThemeContext';
import { TimezoneProvider } from './context/TimezoneContext';
import { PageTitleProvider } from './context/PageTitleContext';
import Login from './components/Login';
import NotFound from './components/NotFound';
import Layout from './components/Layout';

const Dashboard = lazy(() => import('./components/Dashboard'));
const ComputerList = lazy(() => import('./components/ComputerList'));
const ComputerDetail = lazy(() => import('./components/ComputerDetail'));
const Settings = lazy(() => import('./components/Settings'));
const AdminPanel = lazy(() => import('./components/AdminPanel'));

const ProtectedRoute: React.FC<{ children: JSX.Element }> = ({ children }) => {
  const { isAuthenticated, isLoading } = useAuth();
  if (isLoading) return <div>Загрузка...</div>;
  if (!isAuthenticated) return <Navigate to="/login" replace />;
  return children;
};

const App: React.FC = () => {
  const {isAuthenticated,  isLoading } = useAuth();

  if (isLoading) return <div>Загрузка...</div>;

  return (
    <ThemeProvider>
      <TimezoneProvider>
        <PageTitleProvider>
          <Routes>
            <Route path="/login" element={<Login />} />
            <Route
              path="*"
              element={
              isAuthenticated ? (
                <Suspense fallback={<div>Загрузка...</div>}>
                  <Layout>
                    <Routes>
                      <Route path="/" element={<ProtectedRoute><Dashboard /></ProtectedRoute>} />
                      <Route path="/computers" element={<ProtectedRoute><ComputerList /></ProtectedRoute>} />
                      <Route path="/computer/:computerId" element={<ProtectedRoute><ComputerDetail /></ProtectedRoute>} />
                      <Route path="/settings" element={<ProtectedRoute><Settings /></ProtectedRoute>} />
                      <Route path="/admin" element={<ProtectedRoute><AdminPanel /></ProtectedRoute>} />
                      <Route path="*" element={<NotFound />} />
                    </Routes>
                  </Layout>
                </Suspense>
                          ) : (
            <Navigate to="/login" replace />
          )
              }
            />
          </Routes>
        </PageTitleProvider>
      </TimezoneProvider>
    </ThemeProvider>
  );
};

export default App;