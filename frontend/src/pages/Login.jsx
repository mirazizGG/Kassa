import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import api from '../api/axios';
import { Lock, User, Loader2, Eye, EyeOff } from 'lucide-react';
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Card, CardContent, CardDescription, CardFooter, CardHeader, CardTitle } from "@/components/ui/card";
import { Label } from "@/components/ui/label";
import { toast } from "sonner";
import { ModeToggle } from '../components/mode-toggle';

const Login = () => {
    const [username, setUsername] = useState('');
    const [password, setPassword] = useState('');
    const [showPassword, setShowPassword] = useState(false);
    const [loading, setLoading] = useState(false);
    const navigate = useNavigate();

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

            const { access_token, role, username: user } = response.data;
            localStorage.setItem('token', access_token);
            localStorage.setItem('role', role);
            localStorage.setItem('username', user);

            toast.success("Muvaffaqiyatli kirildi!", {
                description: `Xush kelibsiz, ${user}`
            });
            navigate('/');
        } catch (err) {
            toast.error("Xatolik!", {
                description: err.response?.data?.detail || "Login yoki parol noto'g'ri."
            });
        } finally {
            setLoading(false);
        }
    };

    return (
        <div className="flex min-h-screen w-full items-center justify-center bg-background px-4">
            <div className="absolute inset-0 bg-grid-slate-200 dark:bg-grid-slate-800 [mask-image:linear-gradient(0deg,white,rgba(255,255,255,0.6))] dark:[mask-image:linear-gradient(0deg,hsl(var(--background)),rgba(0,0,0,0.6))] -z-10"></div>
            <div className="absolute top-4 right-4">
                <ModeToggle />
            </div>

            <Card className="w-full max-w-[400px] shadow-2xl border bg-card/80 backdrop-blur-xl">
                <CardHeader className="space-y-1 text-center pb-8">
                    <div className="mx-auto bg-primary w-12 h-12 rounded-xl flex items-center justify-center text-primary-foreground font-bold text-2xl mb-4 shadow-lg shadow-primary/30">
                        K
                    </div>
                    <CardTitle className="text-2xl font-bold tracking-tight">Xush Kelibsiz</CardTitle>
                    <CardDescription>
                        Kassa tizimiga kirish uchun ma'lumotlarni kiriting
                    </CardDescription>
                </CardHeader>
                <form onSubmit={handleLogin}>
                    <CardContent className="grid gap-6">
                        <div className="grid gap-2">
                            <Label htmlFor="username">Foydalanuvchi nomi</Label>
                            <div className="relative">
                                <User className="absolute left-3 top-2.5 h-4 w-4 text-muted-foreground" />
                                <Input
                                    id="username"
                                    placeholder="admin"
                                    className="pl-9 h-11"
                                    value={username}
                                    onChange={(e) => setUsername(e.target.value)}
                                    required
                                />
                            </div>
                        </div>
                        <div className="grid gap-2">
                            <Label htmlFor="password">Parol</Label>
                            <div className="relative">
                                <Lock className="absolute left-3 top-2.5 h-4 w-4 text-muted-foreground" />
                                <Input
                                    id="password"
                                    type={showPassword ? "text" : "password"}
                                    placeholder="••••••••"
                                    className="pl-9 pr-10 h-11"
                                    value={password}
                                    onChange={(e) => setPassword(e.target.value)}
                                    required
                                />
                                <Button
                                    type="button"
                                    variant="ghost"
                                    size="icon"
                                    className="absolute right-0 top-0 h-full px-3 py-2 hover:bg-transparent text-muted-foreground"
                                    onClick={() => setShowPassword(!showPassword)}
                                >
                                    {showPassword ? (
                                        <EyeOff className="h-4 w-4" />
                                    ) : (
                                        <Eye className="h-4 w-4" />
                                    )}
                                </Button>
                            </div>
                        </div>
                    </CardContent>
                    <CardFooter className="pt-2">
                        <Button
                            type="submit"
                            className="w-full h-11 text-base font-semibold transition-all hover:scale-[1.01] active:scale-[0.99]"
                            disabled={loading}
                        >
                            {loading ? (
                                <>
                                    <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                                    Kirilmoqda...
                                </>
                            ) : (
                                "Tizimga kirish"
                            )}
                        </Button>
                    </CardFooter>
                </form>
            </Card>
        </div>
    );
};

export default Login;
