import React from 'react';
import { BrowserRouter as Router, Routes, Route, Navigate } from 'react-router-dom';
import { QueryClientProvider } from '@tanstack/react-query';
import { queryClient } from './api/queryClient';
import Layout from './components/Layout';
import ErrorBoundary from './components/ErrorBoundary';
import { Toaster } from "@/components/ui/sonner";
import { ThemeProvider } from "@/components/theme-provider";
import TitleBar from './components/TitleBar';

const Login = React.lazy(() => import('./pages/Login'));
const Dashboard = React.lazy(() => import('./pages/Dashboard'));
const POS = React.lazy(() => import('./pages/POS'));
const Inventory = React.lazy(() => import('./pages/Inventory'));
const CRM = React.lazy(() => import('./pages/CRM'));
const Finance = React.lazy(() => import('./pages/Finance'));
const Employees = React.lazy(() => import('./pages/Employees'));
const Attendance = React.lazy(() => import('./pages/Attendance'));
const ShiftHistory = React.lazy(() => import('./pages/ShiftHistory'));
const SalesHistory = React.lazy(() => import('./pages/SalesHistory'));
const AuditLogs = React.lazy(() => import('./pages/AuditLogs'));
const Suppliers = React.lazy(() => import('./pages/Suppliers'));
const Settings = React.lazy(() => import('./pages/Settings'));

const ProtectedRoute = ({ children }) => {
  const token = localStorage.getItem('token');
  return token ? children : <Navigate to="/login" />;
};

const RoleProtectedRoute = ({ children, allowedRoles }) => {
  const token = localStorage.getItem('token');
  const role = localStorage.getItem('role');

  if (!token) return <Navigate to="/login" />;
  if (!allowedRoles.includes(role)) return <Navigate to="/" />;

  return children;
};

const PageLoader = () => (
  <div className="p-8 text-center text-muted-foreground">Yuklanmoqda...</div>
);

function App() {
  return (
    <ErrorBoundary>
      <QueryClientProvider client={queryClient}>
        <ThemeProvider defaultTheme="light" storageKey="vite-ui-theme">
          <div className="flex h-screen flex-col">
            <TitleBar />
            <div className="min-h-0 flex-1">
              <Router>
                <React.Suspense fallback={<PageLoader />}>
                  <Routes>
                    <Route path="/login" element={<Login />} />
                    <Route path="/" element={<ProtectedRoute><Layout /></ProtectedRoute>}>
                      <Route index element={<Dashboard />} />
                      <Route path="pos" element={<POS />} />
                      <Route path="inventory" element={<RoleProtectedRoute allowedRoles={['admin', 'manager', 'warehouse']}><Inventory /></RoleProtectedRoute>} />
                      <Route path="crm" element={<CRM />} />
                      <Route path="finance" element={<RoleProtectedRoute allowedRoles={['admin', 'manager']}><Finance /></RoleProtectedRoute>} />
                      <Route path="employees" element={<RoleProtectedRoute allowedRoles={['admin', 'manager']}><Employees /></RoleProtectedRoute>} />
                      <Route path="attendance" element={<RoleProtectedRoute allowedRoles={['admin', 'manager']}><Attendance /></RoleProtectedRoute>} />
                      <Route path="shifts" element={<ShiftHistory />} />
                      <Route path="sales" element={<SalesHistory />} />
                      <Route path="suppliers" element={<RoleProtectedRoute allowedRoles={['admin', 'manager', 'warehouse']}><Suppliers /></RoleProtectedRoute>} />
                      <Route path="audit" element={<RoleProtectedRoute allowedRoles={['admin']}><AuditLogs /></RoleProtectedRoute>} />
                      <Route path="settings" element={<RoleProtectedRoute allowedRoles={['admin']}><Settings /></RoleProtectedRoute>} />
                    </Route>
                  </Routes>
                </React.Suspense>
              </Router>
            </div>
          </div>
          <Toaster />
        </ThemeProvider>
      </QueryClientProvider>
    </ErrorBoundary>
  );
}

export default App;