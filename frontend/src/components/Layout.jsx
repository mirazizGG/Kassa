import React from 'react';
import { NavLink, Outlet, useNavigate } from 'react-router-dom';
import {
    LayoutDashboard,
    ShoppingCart,
    Package,
    Users,
    PieChart,
    LogOut,
    Bell,
    Search,
    User,
    Menu,
    Settings
} from 'lucide-react';
import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import { Avatar, AvatarFallback, AvatarImage } from "@/components/ui/avatar";
import { Input } from "@/components/ui/input";
import {
    DropdownMenu,
    DropdownMenuContent,
    DropdownMenuItem,
    DropdownMenuLabel,
    DropdownMenuSeparator,
    DropdownMenuTrigger
} from "@/components/ui/dropdown-menu";

const NavItem = ({ to, icon: Icon, children }) => (
    <NavLink
        to={to}
        className={({ isActive }) => cn(
            "flex items-center gap-3 px-3 py-2 rounded-lg transition-all duration-200 group",
            isActive
                ? "bg-primary text-primary-foreground shadow-md"
                : "text-muted-foreground hover:bg-muted hover:text-foreground"
        )}
    >
        <Icon className={cn("w-5 h-5", "group-hover:scale-110 transition-transform")} />
        <span className="font-medium">{children}</span>
    </NavLink>
);

const Layout = () => {
    const navigate = useNavigate();
    const username = localStorage.getItem('username') || 'Admin';
    const role = localStorage.getItem('role') || 'User';

    const handleLogout = () => {
        localStorage.clear();
        navigate('/login');
    };

    return (
        <div className="flex h-screen w-full bg-slate-50/50">
            {/* Sidebar */}
            <aside className="w-64 border-r bg-white/80 backdrop-blur-xl flex flex-col shrink-0">
                <div className="p-6">
                    <div className="flex items-center gap-3 px-2 py-1">
                        <div className="bg-primary w-8 h-8 rounded-lg flex items-center justify-center text-white font-bold text-xl">
                            K
                        </div>
                        <h2 className="text-xl font-bold tracking-tight text-slate-900">Kassa Pro</h2>
                    </div>
                </div>

                <nav className="flex-1 px-4 space-y-1 overflow-y-auto">
                    <NavItem to="/" icon={LayoutDashboard}>Dashboard</NavItem>
                    <NavItem to="/pos" icon={ShoppingCart}>Sotuv (POS)</NavItem>
                    <NavItem to="/inventory" icon={Package}>Ombor</NavItem>
                    <NavItem to="/crm" icon={Users}>Mijozlar</NavItem>
                    <NavItem to="/finance" icon={PieChart}>Moliya</NavItem>
                </nav>

                <div className="p-4 border-t">
                    <Button
                        variant="ghost"
                        className="w-full justify-start gap-3 text-muted-foreground hover:text-destructive hover:bg-destructive/10"
                        onClick={handleLogout}
                    >
                        <LogOut className="w-5 h-5" />
                        <span>Chiqish</span>
                    </Button>
                </div>
            </aside>

            {/* Main Content */}
            <main className="flex-1 flex flex-col min-w-0 overflow-hidden">
                {/* Topbar */}
                <header className="h-16 border-b bg-white/80 backdrop-blur-xl flex items-center justify-between px-8 shrink-0">
                    <div className="flex items-center flex-1 max-w-md">
                        <div className="relative w-full">
                            <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-muted-foreground" />
                            <Input
                                placeholder="Qidiruv..."
                                className="pl-10 bg-slate-100/50 border-none focus-visible:ring-1 focus-visible:ring-primary h-9"
                            />
                        </div>
                    </div>

                    <div className="flex items-center gap-4">
                        <Button variant="ghost" size="icon" className="relative text-muted-foreground">
                            <Bell className="w-5 h-5" />
                            <span className="absolute top-2 right-2 w-2 h-2 bg-destructive rounded-full border-2 border-white"></span>
                        </Button>

                        <DropdownMenu>
                            <DropdownMenuTrigger asChild>
                                <Button variant="ghost" className="relative h-10 flex items-center gap-3 pl-1 pr-2 rounded-full hover:bg-muted/50 transition-colors">
                                    <Avatar className="h-8 w-8 border shadow-sm">
                                        <AvatarFallback className="bg-primary/10 text-primary font-semibold">
                                            {username[0]?.toUpperCase()}
                                        </AvatarFallback>
                                    </Avatar>
                                    <div className="hidden md:flex flex-col items-start leading-none gap-1 mr-1">
                                        <span className="text-sm font-semibold">{username}</span>
                                        <span className="text-[10px] uppercase font-bold text-muted-foreground tracking-wider">{role}</span>
                                    </div>
                                </Button>
                            </DropdownMenuTrigger>
                            <DropdownMenuContent align="end" className="w-56 mt-2">
                                <DropdownMenuLabel>Mening Profilim</DropdownMenuLabel>
                                <DropdownMenuSeparator />
                                <DropdownMenuItem className="gap-2">
                                    <User className="w-4 h-4" /> Profil
                                </DropdownMenuItem>
                                <DropdownMenuItem className="gap-2">
                                    <Settings className="w-4 h-4" /> Sozlamalar
                                </DropdownMenuItem>
                                <DropdownMenuSeparator />
                                <DropdownMenuItem className="text-destructive gap-2 focus:bg-destructive/10 focus:text-destructive" onClick={handleLogout}>
                                    <LogOut className="w-4 h-4" /> Chiqish
                                </DropdownMenuItem>
                            </DropdownMenuContent>
                        </DropdownMenu>
                    </div>
                </header>

                {/* Page Area */}
                <div className="flex-1 overflow-auto p-8 bg-slate-50/50">
                    <div className="max-w-7xl mx-auto h-full">
                        <Outlet />
                    </div>
                </div>
            </main>
        </div>
    );
};

export default Layout;
