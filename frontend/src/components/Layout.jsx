import React, { useState } from 'react';
import { Outlet, NavLink, useNavigate, useLocation } from 'react-router-dom';
import {
  LayoutDashboard,
  ShoppingCart,
  Package,
  Users,
  LogOut,
  Menu,
  X,
  CreditCard,
  UserCog,
  History,
  Activity
} from 'lucide-react';
import { Button } from "@/components/ui/button";

const Layout = () => {
  const navigate = useNavigate();
  const location = useLocation();
  const [isSidebarOpen, setIsSidebarOpen] = useState(true);

  const handleLogout = () => {
    localStorage.removeItem('token');
    localStorage.removeItem('role');
    navigate('/login');
  };

  const role = localStorage.getItem('role');

  const navItems = [
    { path: '/', label: 'Asosiy', icon: LayoutDashboard },
    { path: '/pos', label: 'Sotuv (POS)', icon: ShoppingCart },
    { path: '/inventory', label: 'Ombor', icon: Package },
    { path: '/crm', label: 'Mijozlar', icon: Users },
    ...(role === 'admin' || role === 'manager' ? [{ path: '/finance', label: 'Moliya', icon: CreditCard }] : []),
    { path: '/shifts', label: 'Smena Tarixi', icon: History },
    { path: '/sales', label: 'Savdolar Tarixi', icon: ShoppingCart },
    ...(role === 'admin' ? [{ path: '/audit', label: 'Audit', icon: Activity }] : []),
    ...(role === 'admin' || role === 'manager' ? [
        { path: '/employees', label: 'Xodimlar', icon: UserCog },
        { path: '/suppliers', label: 'Firmalar', icon: Package }
    ] : []),
    ...(role === 'admin' ? [{ path: '/settings', label: 'Sozlamalar', icon: UserCog }] : []),
  ];

  return (
    <div className="flex h-screen w-full bg-background transition-colors duration-300">
      {/* Sidebar */}
      {/* Sidebar - Hide for Cashier */}
      {role !== 'cashier' && (
      <aside
        className={`${isSidebarOpen ? 'w-64' : 'w-20'} 
          bg-card border-r border-border transition-all duration-300 flex flex-col h-full shadow-xl z-50`}
      >
        <div className="h-16 flex items-center justify-between px-4 border-b border-border">
          {isSidebarOpen ? (
            <h1 className="text-xl font-bold bg-gradient-to-r from-primary to-purple-600 bg-clip-text text-transparent truncate">
              SmartKassa
            </h1>
          ) : (
            <div className="w-8 h-8 rounded-lg bg-primary flex items-center justify-center text-primary-foreground font-bold">
              SK
            </div>
          )}
          <Button
            variant="ghost"
            size="icon"
            onClick={() => setIsSidebarOpen(!isSidebarOpen)}
            className="text-muted-foreground hover:bg-accent hover:text-accent-foreground"
          >
            {isSidebarOpen ? <X className="w-5 h-5" /> : <Menu className="w-5 h-5" />}
          </Button>
        </div>

        <nav className="flex-1 overflow-y-auto py-6 px-3 space-y-2">
          {navItems.map((item) => (
            <NavLink
              key={item.path}
              to={item.path}
              className={({ isActive }) =>
                `flex items-center gap-3 px-3 py-3 rounded-xl transition-all duration-200 group
                ${isActive
                  ? 'bg-primary text-primary-foreground shadow-lg shadow-primary/25 font-semibold'
                  : 'text-muted-foreground hover:bg-accent hover:text-accent-foreground'
                }`
              }
            >
              <item.icon className={`w-5 h-5 ${!isSidebarOpen && 'mx-auto'}`} />
              {isSidebarOpen && <span>{item.label}</span>}
              
              {!isSidebarOpen && (
                 <div className="absolute left-16 bg-popover text-popover-foreground px-2 py-1 rounded-md text-sm opacity-0 group-hover:opacity-100 transition-opacity whitespace-nowrap shadow-md pointer-events-none z-50 ml-2 border">
                    {item.label}
                 </div>
              )}
            </NavLink>
          ))}
        </nav>

        <div className="mt-auto p-4 border-t border-border space-y-4">
            {/* User Profile Info */}
            <div className={`flex items-center gap-3 px-2 py-2 rounded-xl bg-muted/50 border border-border/50 ${!isSidebarOpen && 'justify-center px-0'}`}>
                <div className="w-8 h-8 rounded-full bg-primary/20 flex items-center justify-center text-primary shrink-0">
                    <Users className="w-4 h-4" />
                </div>
                {isSidebarOpen && (
                    <div className="flex flex-col overflow-hidden">
                        <span className="text-sm font-bold truncate text-foreground leading-tight">
                            {localStorage.getItem('username') || 'Foydalanuvchi'}
                        </span>
                        <span className="text-[10px] uppercase tracking-wider font-bold text-muted-foreground leading-tight mt-0.5">
                            {role === 'admin' ? 'Administrator' : role === 'manager' ? 'Menejer' : 'Kassir'}
                        </span>
                    </div>
                )}
            </div>

            <Button
                variant="destructive"
                className={`w-full justify-start gap-3 rounded-xl shadow-lg shadow-destructive/10 transition-all hover:scale-[1.02] active:scale-95 ${!isSidebarOpen && 'justify-center px-0'}`}
                onClick={handleLogout}
            >
                <LogOut className="w-5 h-5" />
                {isSidebarOpen && "Chiqish"}
            </Button>
        </div>
      </aside>
      )}

      {/* Main Content */}
      <main className="flex-1 flex flex-col min-w-0 overflow-hidden h-full bg-secondary/20">
        <div className={`flex-1 overflow-auto ${location.pathname === '/pos' ? 'p-0' : 'p-4 md:p-8'} ${role === 'cashier' ? 'pb-20' : ''}`}>
            <div 
                key={location.pathname}
                className={`mx-auto animate-in fade-in slide-in-from-bottom-4 duration-500 ease-in-out ${location.pathname === '/pos' ? 'max-w-none h-full' : 'max-w-7xl'}`}
            >
                <Outlet />
            </div>
            </div>
        
        {/* Bottom Nav for Cashier */}
        {role === 'cashier' && (
            <div className="fixed bottom-0 left-0 right-0 h-16 bg-card border-t border-border flex items-center justify-around z-50 shadow-[0_-4px_6px_-1px_rgba(0,0,0,0.1)]">
                <NavLink to="/pos" className={({ isActive }) => `flex flex-col items-center justify-center w-full h-full gap-1 ${isActive ? 'text-primary' : 'text-muted-foreground hover:text-foreground'}`}>
                    <ShoppingCart className="w-6 h-6" />
                    <span className="text-xs font-medium">Kassa</span>
                </NavLink>
                 <NavLink to="/sales" className={({ isActive }) => `flex flex-col items-center justify-center w-full h-full gap-1 ${isActive ? 'text-primary' : 'text-muted-foreground hover:text-foreground'}`}>
                    <History className="w-6 h-6" />
                    <span className="text-xs font-medium">Tarix</span>
                </NavLink>
                <NavLink to="/crm" className={({ isActive }) => `flex flex-col items-center justify-center w-full h-full gap-1 ${isActive ? 'text-primary' : 'text-muted-foreground hover:text-foreground'}`}>
                    <Users className="w-6 h-6" />
                    <span className="text-xs font-medium">Mijozlar</span>
                </NavLink>
                <button onClick={handleLogout} className="flex flex-col items-center justify-center w-full h-full gap-1 text-destructive hover:bg-destructive/10">
                    <LogOut className="w-6 h-6" />
                    <span className="text-xs font-medium">Chiqish</span>
                </button>
            </div>
        )}
      </main>
    </div>
  );
};

export default Layout;
