
import React from 'react';
import { BrowserRouter as Router, Routes, Route, Navigate } from 'react-router-dom';
import { QueryClientProvider } from '@tanstack/react-query';
import { queryClient } from './api/queryClient';
import Layout from './components/Layout';
import Login from './pages/Login';
import Dashboard from './pages/Dashboard';
import POS from './pages/POS';
import Inventory from './pages/Inventory';
import CRM from './pages/CRM';
import Finance from './pages/Finance';
import Employees from './pages/Employees';
import ShiftHistory from './pages/ShiftHistory';
import SalesHistory from './pages/SalesHistory';
import AuditLogs from './pages/AuditLogs';
import ErrorBoundary from './components/ErrorBoundary';

import { Toaster } from "@/components/ui/sonner";
import { ThemeProvider } from "@/components/theme-provider"

const ProtectedRoute = ({ children }) => {
  const token = localStorage.getItem('token');
  return token ? children : <Navigate to="/login" />;
};

function App() {
  return (
    <ErrorBoundary>
      <QueryClientProvider client={queryClient}>
        <ThemeProvider defaultTheme="light" storageKey="vite-ui-theme">
          <Router>
            <Routes>
              <Route path="/login" element={<Login />} />
              <Route path="/" element={<ProtectedRoute><Layout /></ProtectedRoute>}>
                <Route index element={<Dashboard />} />
                <Route path="pos" element={<POS />} />
                <Route path="inventory" element={<Inventory />} />
                <Route path="crm" element={<CRM />} />
                <Route path="finance" element={<Finance />} />
                <Route path="employees" element={<Employees />} />
                <Route path="shifts" element={<ShiftHistory />} />
                <Route path="sales" element={<SalesHistory />} />
                <Route path="audit" element={<AuditLogs />} />
              </Route>
            </Routes>
          </Router>
          <Toaster />
        </ThemeProvider>
      </QueryClientProvider>
    </ErrorBoundary>
  );
}

export default App;
