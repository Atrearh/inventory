// front/src/App.tsx
import React, { Suspense, lazy } from 'react';
import { Routes, Route, Navigate } from 'react-router-dom';
import { useAuth } from './context/AuthContext';
import Login from './components/Login';
import NotFound from './components/NotFound';
import Layout from './components/Layout';

// Ледаче завантаження компонентів
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
  const { isAuthenticated, isLoading } = useAuth();

  if (isLoading) return <div>Загрузка...</div>;

  return (
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
  );
};

export default App;