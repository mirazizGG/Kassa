import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import api from '../api/axios';
import { Lock, User, Loader2, Eye, EyeOff } from 'lucide-react';
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Card, CardContent, CardDescription, CardFooter, CardHeader, CardTitle } from "@/components/ui/card";
import { Label } from "@/components/ui/label";
import { toast } from "sonner";

const Login = () => {
    const [username, setUsername] = useState('');
    const [password, setPassword] = useState('');
    const [showPassword, setShowPassword] = useState(false);
    const [loading, setLoading] = useState(false);
    const navigate = useNavigate();

    useEffect(() => {
        // Force light mode on login page
        document.documentElement.classList.remove('dark');
    }, []);

    const handleLogin = async (e) => {
        e.preventDefault();
        setLoading(true);

        try {
            const params = new URLSearchParams();
            params.append('username', username);
            params.append('password', password);

            const response = await api.post('/auth/token', params, {
                headers: { 'Content-Type': 'application/x-www-form-urlencoded' }
            });

            const { access_token, role, username: user, user_id, permissions } = response.data;
            localStorage.setItem('token', access_token);
            localStorage.setItem('role', role);
            localStorage.setItem('username', user);
            localStorage.setItem('userId', user_id);
            localStorage.setItem('permissions', permissions || '');

            toast.success("Muvaffaqiyatli kirildi!", {
                description: `Xush kelibsiz, ${user}`
            });

            if (role === 'cashier') {
                navigate('/pos');
            } else if (role === 'warehouse') {
                navigate('/inventory');
            } else {
                navigate('/');
            }
        } catch (err) {
            toast.error("Xatolik!", {
                description: err.response?.data?.detail || "Login yoki parol noto'g'ri."
            });
        } finally {
            setLoading(false);
        }
    };

    return (
        <div className="w-full min-h-screen grid lg:grid-cols-[35%_65%]">
            {/* Left Side - Branding (Hidden on mobile) */}
            <div className="hidden lg:flex flex-col justify-center items-center bg-zinc-900 text-white p-8 relative overflow-hidden">
                <div className="absolute inset-0 bg-[radial-gradient(#ffffff33_1px,transparent_1px)] [background-size:24px_24px] opacity-20"></div>
                <div className="relative z-10 flex flex-col items-center text-center">
                    <div className="w-20 h-20 bg-white/10 rounded-2xl flex items-center justify-center mb-6 backdrop-blur-sm border border-white/10 shadow-2xl">
                        <svg
                            xmlns="http://www.w3.org/2000/svg"
                            viewBox="0 0 24 24"
                            fill="none"
                            stroke="currentColor"
                            strokeWidth="2"
                            strokeLinecap="round"
                            strokeLinejoin="round"
                            className="w-10 h-10"
                        >
                            <path d="M3 9l9-7 9 7v11a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z" />
                            <polyline points="9 22 9 12 15 12 15 22" />
                        </svg>
                    </div>
                    <h1 className="text-4xl font-bold mb-3 tracking-tight">SmartKassa</h1>
                    <p className="text-zinc-400 text-lg max-w-sm leading-relaxed">
                        Savdoni avtomatlashtirish yagona tizimi.
                    </p>
                </div>
                {/* Decorative circles */}
                <div className="absolute -bottom-24 -left-24 w-64 h-64 bg-primary/20 rounded-full blur-3xl"></div>
                <div className="absolute -top-24 -right-24 w-64 h-64 bg-purple-500/20 rounded-full blur-3xl"></div>
            </div>

            {/* Right Side - Login Form */}
            <div className="flex items-center justify-center bg-white p-8">
                <div className="w-full max-w-md space-y-8">
                    <div className="text-center space-y-2">
                        <h2 className="text-4xl font-bold tracking-tight text-gray-900">Xush Kelibsiz</h2>
                        <p className="text-lg text-muted-foreground">Tizimga kirish uchun ma'lumotlaringizni kiriting</p>
                    </div>

                    <form onSubmit={handleLogin} className="space-y-6">
                        <div className="space-y-3">
                            <Label htmlFor="username" className="text-lg font-medium text-gray-700">Foydalanuvchi nomi</Label>
                            <div className="relative">
                                <User className="absolute left-4 top-4 h-6 w-6 text-gray-400" />
                                <Input
                                    id="username"
                                    placeholder="admin"
                                    className="pl-12 h-14 text-xl bg-gray-50 border-gray-200 focus-visible:ring-primary focus-visible:border-primary transition-all rounded-xl"
                                    value={username}
                                    onChange={(e) => setUsername(e.target.value)}
                                    required
                                />
                            </div>
                        </div>

                        <div className="space-y-3">
                            <div className="flex items-center justify-between">
                                <Label htmlFor="password" className="text-lg font-medium text-gray-700">Parol</Label>
                            </div>
                            <div className="relative">
                                <Lock className="absolute left-4 top-4 h-6 w-6 text-gray-400" />
                                <Input
                                    id="password"
                                    type={showPassword ? "text" : "password"}
                                    placeholder="••••••••"
                                    className="pl-12 pr-14 h-14 text-xl bg-gray-50 border-gray-200 focus-visible:ring-primary focus-visible:border-primary transition-all rounded-xl"
                                    value={password}
                                    onChange={(e) => setPassword(e.target.value)}
                                    required
                                />
                                <Button
                                    type="button"
                                    variant="ghost"
                                    size="icon"
                                    className="absolute right-0 top-0 h-full px-4 text-gray-400 hover:text-gray-600 hover:bg-transparent"
                                    onClick={() => setShowPassword(!showPassword)}
                                >
                                    {showPassword ? (
                                        <EyeOff className="h-6 w-6" />
                                    ) : (
                                        <Eye className="h-6 w-6" />
                                    )}
                                </Button>
                            </div>
                        </div>

                        <Button 
                            type="submit" 
                            className="w-full h-14 text-xl font-bold bg-primary hover:bg-primary/90 transition-all shadow-lg shadow-primary/20 rounded-xl mt-4"
                            disabled={loading}
                        >
                            {loading ? (
                                <>
                                    <Loader2 className="mr-3 h-6 w-6 animate-spin" />
                                    Kirilmoqda...
                                </>
                            ) : (
                                "Tizimga kirish"
                            )}
                        </Button>
                    </form>
                    
                    <p className="px-8 text-center text-sm text-muted-foreground">
                       SmartKassa &copy; 2024
                    </p>
                </div>
            </div>
        </div>
    );
};

export default Login;
