import React, { useState } from 'react';
import { useQuery, useMutation } from '@tanstack/react-query';
import api from '../api/axios';
import { queryClient } from '../api/queryClient';
import {
    Plus, 
    UserPlus, 
    CheckCircle2, 
    Clock, 
    MoreHorizontal,
    Trash,
    Users,
    User,
    CheckSquare,
    Calendar,
    TrendingUp,
    BarChart3,
    Ban,
    UserCheck,
    Eye,
    EyeOff
} from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Badge } from "@/components/ui/badge";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import {
    Dialog,
    DialogContent,
    DialogDescription,
    DialogFooter,
    DialogHeader,
    DialogTitle,
    DialogTrigger
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
    Select,
    SelectContent,
    SelectItem,
    SelectTrigger,
    SelectValue,
} from "@/components/ui/select";
import { 
    DropdownMenu, 
    DropdownMenuContent, 
    DropdownMenuItem, 
    DropdownMenuTrigger 
} from "@/components/ui/dropdown-menu";
import { toast } from "sonner";

const Employees = () => {
    const role = localStorage.getItem('role');
    const currentUserId = parseInt(localStorage.getItem('userId')); // Assuming userId is stored
    const [isTaskModalOpen, setIsTaskModalOpen] = useState(false);
    const [isEmployeeModalOpen, setIsEmployeeModalOpen] = useState(false);
    const [isEditModalOpen, setIsEditModalOpen] = useState(false);
    const [isDeleteConfirmOpen, setIsDeleteConfirmOpen] = useState(false);
    
    const [showPasswordNew, setShowPasswordNew] = useState(false);
    const [showPasswordEdit, setShowPasswordEdit] = useState(false);
    
    const [editingEmployee, setEditingEmployee] = useState(null);
    const [deletingEmployee, setDeletingEmployee] = useState(null);
    const [newEmployee, setNewEmployee] = useState({
        username: '',
        password: '',
        role: 'cashier',
        full_name: '',
        phone: '',
        address: '',
        passport: '',
        notes: '',
        permissions: 'pos'
    });

    const [newTask, setNewTask] = useState({
        title: '',
        description: '',
        assigned_to: '',
        due_date: ''
    });

    // --- QUERIES ---
    const { data: employees = [], isLoading: isEmployeesLoading } = useQuery({
        queryKey: ['employees'],
        queryFn: async () => {
            const res = await api.get('/auth/employees');
            return res.data;
        }
    });

    const { data: tasks = [], isLoading: isTasksLoading } = useQuery({
        queryKey: ['tasks'],
        queryFn: async () => {
            const res = await api.get('/tasks');
            return res.data;
        }
    });

    const { data: performance = [], isLoading: isPerformanceLoading } = useQuery({
        queryKey: ['employee-performance'],
        queryFn: async () => {
            const res = await api.get('/finance/employee-performance');
            return res.data;
        }
    });

    // --- MUTATIONS ---
    const createEmployeeMutation = useMutation({
        mutationFn: (data) => api.post('/auth/employees', data),
        onSuccess: () => {
             queryClient.invalidateQueries(['employees']);
             setIsEmployeeModalOpen(false);
             setNewEmployee({ 
                 username: '', 
                 password: '', 
                 role: 'cashier', 
                 full_name: '', 
                 phone: '', 
                 address: '', 
                 passport: '', 
                 notes: '', 
                 permissions: 'pos' 
             });
             toast.success("Xodim qo'shildi!");
        },
        onError: (err) => {
             const detail = err.response?.data?.detail;
             const errorMessage = typeof detail === 'string' 
                ? detail 
                : (Array.isArray(detail) ? detail.map(d => d.msg).join(", ") : "Xodim qo'shib bo'lmadi");
             toast.error("Xatolik", { description: errorMessage });
        }
    });

    const updateEmployeeMutation = useMutation({
        mutationFn: (data) => api.patch(`/auth/employees/${data.id}`, data),
        onSuccess: (res) => {
             const updatedEmp = res.data;
             queryClient.invalidateQueries(['employees']);
             
             // Agar o'zimizni tahrirlagan bo'lsak, localStorage ni ham yangilaymiz
             if (updatedEmp.id === currentUserId) {
                 localStorage.setItem('role', updatedEmp.role);
                 localStorage.setItem('permissions', updatedEmp.permissions || '');
                 // Sidebar va Router o'zgarishi uchun sahifani reload qilish tavsiya etiladi
                 // yoki Layout.jsx bunga qarab ishlashi kerak. Eng osoni reload.
                 window.location.reload();
             }

             setIsEditModalOpen(false);
             setEditingEmployee(null);
             toast.success("Xodim ma'lumotlari yangilandi!");
        },
        onError: (err) => {
             const detail = err.response?.data?.detail;
             const errorMessage = typeof detail === 'string' 
                ? detail 
                : (Array.isArray(detail) ? detail.map(d => d.msg).join(", ") : "Xatolik yuz berdi");
             toast.error("Xatolik", { description: errorMessage });
        }
    });

    const deleteEmployeeMutation = useMutation({
        mutationFn: (id) => api.delete(`/auth/employees/${id}`),
        onSuccess: () => {
             queryClient.invalidateQueries(['employees']);
             setIsDeleteConfirmOpen(false);
             setDeletingEmployee(null);
             toast.success("Xodim tizimdan o'chirildi");
        },
        onError: (err) => {
             const detail = err.response?.data?.detail;
             const errorMessage = typeof detail === 'string' 
                ? detail 
                : (Array.isArray(detail) ? detail.map(d => d.msg).join(", ") : "Xatolik yuz berdi");
             toast.error("O'chirishda xatolik", { description: errorMessage });
        }
    });

    // --- MUTATIONS ---
    const createTaskMutation = useMutation({
        mutationFn: (data) => api.post('/tasks', data),
        onSuccess: () => {
             queryClient.invalidateQueries(['tasks']);
             setIsTaskModalOpen(false);
             setNewTask({ title: '', description: '', assigned_to: '', due_date: '' });
             toast.success("Vazifa yaratildi");
        },
        onError: (err) => {
             const detail = err.response?.data?.detail;
             const errorMessage = typeof detail === 'string' 
                ? detail 
                : (Array.isArray(detail) ? detail.map(d => d.msg).join(", ") : "Vazifa yaratib bo'lmadi");
             
             toast.error("Xatolik", { description: errorMessage });
        }
    });

    const handleCreateTask = (e) => {
        e.preventDefault();
        
        if (!newTask.assigned_to) {
            toast.error("Xodimni tanlang");
            return;
        }

        const taskData = {
            title: newTask.title,
            description: newTask.description,
            assigned_to: parseInt(newTask.assigned_to),
        };

        if (newTask.due_date) {
            taskData.due_date = newTask.due_date;
        }

        createTaskMutation.mutate(taskData);
    };

    const handleCreateEmployee = (e) => {
        e.preventDefault();
        createEmployeeMutation.mutate(newEmployee);
    };

    const handleUpdateEmployee = (e) => {
        e.preventDefault();
        
        // Don't send empty password
        const data = { ...editingEmployee };
        if (!data.password) delete data.password;
        
        updateEmployeeMutation.mutate(data);
    };

    return (
        <div className="space-y-6 animate-in fade-in slide-in-from-bottom-4 duration-500">
            <div className="flex items-center justify-between">
                <div>
                    <h1 className="text-3xl font-bold tracking-tight">Xodimlar va Vazifalar</h1>
                    <p className="text-muted-foreground">Jamoa boshqaruvi va topshiriqlar nazorati</p>
                </div>
            </div>

            <Tabs defaultValue="list" className="w-full">
                <TabsList className="grid w-full grid-cols-3 max-w-[500px]">
                    <TabsTrigger value="list" className="gap-2"><Users className="w-4 h-4"/> Xodimlar</TabsTrigger>
                    <TabsTrigger value="tasks" className="gap-2"><CheckSquare className="w-4 h-4"/> Vazifalar</TabsTrigger>
                    <TabsTrigger value="performance" className="gap-2"><TrendingUp className="w-4 h-4"/> Samaradorlik</TabsTrigger>
                </TabsList>

                {/* --- EMPLOYEES LIST CONTENT --- */}
                <TabsContent value="list" className="mt-6">
                    <div className="flex justify-end mb-4">
                        <Dialog open={isEmployeeModalOpen} onOpenChange={setIsEmployeeModalOpen}>
                            <DialogTrigger asChild>
                                <Button className="gap-2 shadow-lg shadow-indigo-500/20" variant="indigo">
                                    <UserPlus className="w-4 h-4" /> Yangi Xodim
                                </Button>
                            </DialogTrigger>
                            <DialogContent className="sm:max-w-[425px]">
                                <form onSubmit={handleCreateEmployee}>
                                    <DialogHeader>
                                        <DialogTitle>Yangi Xodim Qo'shish</DialogTitle>
                                        <DialogDescription>Tizimga kirishi uchun yangi xodim yarating</DialogDescription>
                                    </DialogHeader>
                                    <div className="grid gap-4 py-4">
                                        <div className="grid grid-cols-2 gap-4">
                                            <div className="grid gap-2">
                                                <Label htmlFor="fullname">Ism Sharif</Label>
                                                <Input id="fullname" value={newEmployee.full_name} onChange={e => setNewEmployee({...newEmployee, full_name: e.target.value})} required placeholder="Eshmat Toshmatov" />
                                            </div>
                                            <div className="grid gap-2">
                                                <Label htmlFor="phone">Telefon</Label>
                                                <Input id="phone" value={newEmployee.phone} onChange={e => setNewEmployee({...newEmployee, phone: e.target.value})} required placeholder="+998" />
                                            </div>
                                        </div>
                                        <div className="grid grid-cols-2 gap-4">
                                            <div className="grid gap-2">
                                                <Label htmlFor="username">Login</Label>
                                                <Input id="username" value={newEmployee.username} onChange={e => setNewEmployee({...newEmployee, username: e.target.value})} required placeholder="eshmat123" />
                                            </div>
                                            <div className="grid gap-2">
                                                <Label htmlFor="password">Parol</Label>
                                                <div className="relative">
                                                    <Input 
                                                        id="password" 
                                                        type={showPasswordNew ? "text" : "password"} 
                                                        value={newEmployee.password} 
                                                        onChange={e => setNewEmployee({...newEmployee, password: e.target.value})} 
                                                        required 
                                                        placeholder="••••••" 
                                                        className="pr-10"
                                                    />
                                                    <Button
                                                        type="button"
                                                        variant="ghost"
                                                        size="icon"
                                                        className="absolute right-0 top-0 h-full px-3 text-muted-foreground hover:bg-transparent"
                                                        onClick={() => setShowPasswordNew(!showPasswordNew)}
                                                    >
                                                        {showPasswordNew ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
                                                    </Button>
                                                </div>
                                            </div>
                                        </div>
                                        <div className="grid grid-cols-2 gap-4">
                                            <div className="grid gap-2">
                                                <Label htmlFor="passport">Pasport Seria</Label>
                                                <Input id="passport" value={newEmployee.passport} onChange={e => setNewEmployee({...newEmployee, passport: e.target.value})} required placeholder="AA1234567" />
                                            </div>
                                            <div className="grid gap-2">
                                                <Label htmlFor="address">Manzil</Label>
                                                <Input id="address" value={newEmployee.address} onChange={e => setNewEmployee({...newEmployee, address: e.target.value})} required placeholder="Toshkent sh., ..." />
                                            </div>
                                        </div>
                                        <div className="grid gap-2">
                                            <Label htmlFor="notes">Qo'shimcha izoh</Label>
                                            <Input id="notes" value={newEmployee.notes} onChange={e => setNewEmployee({...newEmployee, notes: e.target.value})} placeholder="Qo'shimcha ma'lumotlar..." />
                                        </div>
                                        <div className="grid gap-2">
                                            <Label>Lavozim</Label>
                                            <Select value={newEmployee.role} onValueChange={(v) => setNewEmployee({...newEmployee, role: v})}>
                                                <SelectTrigger>
                                                    <SelectValue placeholder="Lavozimni tanlang" />
                                                </SelectTrigger>
                                                <SelectContent>
                                                    {role === 'admin' && <SelectItem value="admin">Admin</SelectItem>}
                                                    {(role === 'admin' || role === 'manager') && <SelectItem value="manager">Manager</SelectItem>}
                                                    {(role === 'admin' || role === 'manager') && <SelectItem value="warehouse">Omborchi</SelectItem>}
                                                    <SelectItem value="cashier">Kassir</SelectItem>
                                                </SelectContent>
                                            </Select>
                                        </div>
                                    </div>
                                    <DialogFooter>
                                        <Button type="submit" disabled={createEmployeeMutation.isPending}>
                                            {createEmployeeMutation.isPending ? "Saqlanmoqda..." : "Saqlash"}
                                        </Button>
                                    </DialogFooter>
                                </form>
                            </DialogContent>
                        </Dialog>
                    </div>
                    <Card className="border-none shadow-md overflow-hidden bg-background/60 backdrop-blur-xl">
                        <CardHeader>
                            <CardTitle>Barcha Xodimlar</CardTitle>
                            <CardDescription>Admin, Manager va Kassirlar ro'yxati</CardDescription>
                        </CardHeader>
                        <CardContent className="p-0">
                            <Table>
                                        <TableHeader>
                                            <TableRow>
                                                <TableHead className="pl-6">Ism Sharif</TableHead>
                                                <TableHead>Foydalanuvchi</TableHead>
                                                <TableHead>Lavozim</TableHead>
                                                <TableHead>Telefon</TableHead>
                                                <TableHead>Status</TableHead>
                                                <TableHead className="text-right pr-6">Amallar</TableHead>
                                            </TableRow>
                                        </TableHeader>
                                        <TableBody>
                                            {isEmployeesLoading ? (
                                                <TableRow><TableCell colSpan={6} className="text-center h-24">Yuklanmoqda...</TableCell></TableRow>
                                            ) : employees.map((emp) => (
                                                <TableRow key={emp.id} className="group hover:bg-muted/50 transition-colors odd:bg-muted/10">
                                                    <TableCell className="pl-6 font-medium">{emp.full_name || '-'}</TableCell>
                                                    <TableCell className="text-muted-foreground">@{emp.username}</TableCell>
                                                    <TableCell>
                                                        <Badge variant={emp.role === 'admin' ? 'default' : emp.role === 'manager' ? 'outline' : 'secondary'} className="uppercase text-[10px]">
                                                            {emp.role}
                                                        </Badge>
                                                    </TableCell>
                                                    <TableCell>{emp.phone || '-'}</TableCell>
                                                    <TableCell>
                                                        <span className={`flex items-center gap-2 text-sm font-medium ${emp.is_active ? 'text-emerald-500' : 'text-rose-500'}`}>
                                                            <div className={`w-2 h-2 rounded-full ${emp.is_active ? 'bg-emerald-500' : 'bg-rose-500'}`} /> 
                                                            {emp.is_active ? 'Aktiv' : 'Bloklangan'}
                                                        </span>
                                                    </TableCell>
                                                    <TableCell className="text-right pr-6">
                                                        <DropdownMenu>
                                                            <DropdownMenuTrigger asChild>
                                                                <Button variant="ghost" size="icon">
                                                                    <MoreHorizontal className="w-4 h-4" />
                                                                </Button>
                                                            </DropdownMenuTrigger>
                                                            <DropdownMenuContent align="end">
                                                                {((role === 'admin') || (role === 'manager' && emp.role === 'cashier')) && (
                                                                    <DropdownMenuItem onClick={() => {
                                                                        setEditingEmployee({ ...emp, password: '' });
                                                                        setIsEditModalOpen(true);
                                                                    }}>
                                                                        <UserPlus className="w-4 h-4 mr-2" /> Tahrirlash
                                                                    </DropdownMenuItem>
                                                                )}
                                                                {((role === 'admin' && emp.id !== currentUserId) || (role === 'manager' && emp.role === 'cashier')) && (
                                                                    <DropdownMenuItem 
                                                                        onClick={() => {
                                                                            updateEmployeeMutation.mutate({ 
                                                                                id: emp.id, 
                                                                                is_active: !emp.is_active 
                                                                            });
                                                                        }}
                                                                        className={emp.is_active ? "text-amber-600 focus:text-amber-600 font-medium" : "text-emerald-600 focus:text-emerald-600 font-medium"}
                                                                    >
                                                                        {emp.is_active ? (
                                                                            <><Ban className="w-4 h-4 mr-2" /> Bloklash</>
                                                                        ) : (
                                                                            <><UserCheck className="w-4 h-4 mr-2" /> Faollashtirish</>
                                                                        )}
                                                                    </DropdownMenuItem>
                                                                )}
                                                                {role === 'admin' && emp.id !== currentUserId && emp.username !== 'admin' && (
                                                                    <DropdownMenuItem 
                                                                        className="text-rose-500 focus:text-rose-500"
                                                                        onClick={() => {
                                                                            setDeletingEmployee(emp);
                                                                            setIsDeleteConfirmOpen(true);
                                                                        }}
                                                                    >
                                                                        <Trash className="w-4 h-4 mr-2" /> O'chirish
                                                                    </DropdownMenuItem>
                                                                )}
                                                            </DropdownMenuContent>
                                                        </DropdownMenu>
                                                    </TableCell>
                                                </TableRow>
                                            ))}
                                        </TableBody>
                            </Table>
                        </CardContent>
                    </Card>
                </TabsContent>

                {/* --- TASKS CONTENT --- */}
                <TabsContent value="tasks" className="mt-6">
                     <div className="flex justify-end mb-4">
                        <Dialog open={isTaskModalOpen} onOpenChange={setIsTaskModalOpen}>
                            <DialogTrigger asChild>
                                <Button className="gap-2 shadow-lg shadow-blue-500/20" variant="info">
                                    <Plus className="w-4 h-4" /> Yangi Vazifa
                                </Button>
                            </DialogTrigger>
                            <DialogContent>
                                <form onSubmit={handleCreateTask}>
                                    <DialogHeader>
                                        <DialogTitle>Yangi Vazifa Biriktirish</DialogTitle>
                                        <DialogDescription>Xodimga yangi topshiriq bering</DialogDescription>
                                    </DialogHeader>
                                    <div className="grid gap-4 py-4">
                                        <div className="grid gap-2">
                                            <Label htmlFor="title">Vazifa Nomi</Label>
                                            <Input id="title" value={newTask.title} onChange={e => setNewTask({...newTask, title: e.target.value})} required placeholder="Masalan: Omborini tartiblash" />
                                        </div>
                                        <div className="grid gap-2">
                                            <Label htmlFor="desc">Izoh</Label>
                                            <Input id="desc" value={newTask.description} onChange={e => setNewTask({...newTask, description: e.target.value})} placeholder="Batafsil ma'lumot..." />
                                        </div>
                                        <div className="grid gap-2">
                                            <Label>Mas'ul Xodim</Label>
                                            <Select onValueChange={(v) => setNewTask({...newTask, assigned_to: v})}>
                                                <SelectTrigger>
                                                    <SelectValue placeholder="Xodimni tanlang" />
                                                </SelectTrigger>
                                                <SelectContent>
                                                    {employees.map(emp => (
                                                        <SelectItem key={emp.id} value={emp.id.toString()}>
                                                            {emp.full_name || emp.username}
                                                        </SelectItem>
                                                    ))}
                                                </SelectContent>
                                            </Select>
                                        </div>
                                    </div>
                                    <DialogFooter>
                                        <Button type="submit" disabled={createTaskMutation.isPending}>Saqlash</Button>
                                    </DialogFooter>
                                </form>
                            </DialogContent>
                        </Dialog>
                    </div>

                    <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
                        {isTasksLoading ? (
                            <p>Yuklanmoqda...</p>
                        ) : tasks.length === 0 ? (
                            <div className="col-span-3 text-center p-12 border rounded-xl border-dashed text-muted-foreground">
                                Hozircha vazifalar yo'q
                            </div>
                        ) : tasks.map(task => (
                            <Card key={task.id} className="border-l-4 border-l-primary shadow-sm hover:shadow-md transition-shadow">
                                <CardHeader className="pb-2">
                                    <div className="flex justify-between items-start">
                                        <CardTitle className="text-base font-bold">{task.title}</CardTitle>
                                        <Badge variant={task.status === 'completed' ? 'secondary' : 'outline'} className={task.status === 'completed' ? 'bg-emerald-100 text-emerald-700' : ''}>
                                            {task.status}
                                        </Badge>
                                    </div>
                                    <CardDescription className="line-clamp-2">{task.description}</CardDescription>
                                </CardHeader>
                                <CardContent>
                                    <div className="flex items-center gap-2 text-sm text-muted-foreground mt-2">
                                        <Users className="w-4 h-4" />
                                        {employees.find(e => e.id === task.assigned_to)?.full_name || "Noma'lum"}
                                    </div>
                                    <div className="flex items-center gap-2 text-xs text-muted-foreground mt-1">
                                        <Calendar className="w-3 h-3" />
                                        {new Date(task.created_at).toLocaleDateString()}
                                    </div>
                                </CardContent>
                            </Card>
                        ))}
                    </div>
                </TabsContent>

                {/* --- PERFORMANCE CONTENT --- */}
                <TabsContent value="performance" className="mt-6">
                    <div className="grid gap-6 md:grid-cols-2 lg:grid-cols-3">
                        {isPerformanceLoading ? (
                            <p>Yuklanmoqda...</p>
                        ) : performance.map(emp => (
                            <Card key={emp.id} className="border-none shadow-md bg-background/60 backdrop-blur-xl transition-all hover:shadow-lg">
                                <CardHeader className="pb-2">
                                    <div className="flex items-center gap-3">
                                        <div className="w-10 h-10 rounded-full bg-primary/10 flex items-center justify-center">
                                            <User className="w-5 h-5 text-primary" />
                                        </div>
                                        <div>
                                            <CardTitle className="text-base font-bold">{emp.full_name || emp.username}</CardTitle>
                                            <CardDescription className="text-[10px] uppercase font-semibold">{emp.role}</CardDescription>
                                        </div>
                                    </div>
                                </CardHeader>
                                <CardContent className="space-y-4">
                                    <div className="grid grid-cols-2 gap-4">
                                        <div className="p-3 rounded-xl bg-orange-500/10 border border-orange-500/20">
                                            <div className="text-[10px] text-orange-600 font-bold uppercase mb-1">Savdolar Soni</div>
                                            <div className="text-xl font-bold">{emp.sale_count}</div>
                                        </div>
                                        <div className="p-3 rounded-xl bg-emerald-500/10 border border-emerald-500/20">
                                            <div className="text-[10px] text-emerald-600 font-bold uppercase mb-1">Jami Savdo</div>
                                            <div className="text-xl font-bold truncate" title={`${emp.sale_total.toLocaleString()} so'm`}>
                                                {emp.sale_total >= 1000000 
                                                    ? `${(emp.sale_total / 1000000).toFixed(1)}M` 
                                                    : emp.sale_total.toLocaleString()}
                                            </div>
                                        </div>
                                    </div>
                                    
                                    <div className="space-y-2">
                                        <div className="flex justify-between text-xs font-medium">
                                            <span className="text-muted-foreground">Vazifalar bajarilishi</span>
                                            <span>{emp.completed_tasks} / {emp.total_tasks}</span>
                                        </div>
                                        <div className="h-2 w-full bg-secondary rounded-full overflow-hidden">
                                            <div 
                                                className="h-full bg-primary transition-all duration-500" 
                                                style={{ width: `${emp.total_tasks > 0 ? (emp.completed_tasks / emp.total_tasks) * 100 : 0}%` }}
                                            />
                                        </div>
                                    </div>

                                    <div className="flex items-center justify-between pt-2 border-t text-[10px] text-muted-foreground">
                                        <div className="flex items-center gap-1">
                                            <BarChart3 className="w-3 h-3" />
                                            Oxirgi 30 kunlik ko'rsatkich
                                        </div>
                                    </div>
                                </CardContent>
                            </Card>
                        ))}
                    </div>
                </TabsContent>
            </Tabs>

            {/* --- EDIT EMPLOYEE MODAL --- */}
            <Dialog open={isEditModalOpen} onOpenChange={setIsEditModalOpen}>
                <DialogContent className="sm:max-w-[425px]">
                    <form onSubmit={handleUpdateEmployee}>
                        <DialogHeader>
                            <DialogTitle>Xodim Ma'lumotlarini Tahrirlash</DialogTitle>
                            <DialogDescription>Mavjud xodim ma'lumotlarini yangilang</DialogDescription>
                        </DialogHeader>
                        {editingEmployee && (
                            <div className="grid gap-4 py-4">
                                <div className="grid grid-cols-2 gap-4">
                                    <div className="grid gap-2">
                                        <Label htmlFor="edit-fullname">Ism Sharif</Label>
                                        <Input id="edit-fullname" value={editingEmployee.full_name || ''} onChange={e => setEditingEmployee({...editingEmployee, full_name: e.target.value})} required />
                                    </div>
                                    <div className="grid gap-2">
                                        <Label htmlFor="edit-phone">Telefon</Label>
                                        <Input id="edit-phone" value={editingEmployee.phone || ''} onChange={e => setEditingEmployee({...editingEmployee, phone: e.target.value})} required />
                                    </div>
                                </div>
                                <div className="grid grid-cols-2 gap-4">
                                    <div className="grid gap-2">
                                        <Label htmlFor="edit-username">Login</Label>
                                        <Input id="edit-username" value={editingEmployee.username} onChange={e => setEditingEmployee({...editingEmployee, username: e.target.value})} required />
                                    </div>
                                    <div className="grid gap-2">
                                        <Label htmlFor="edit-password">Yangi Parol (ixtiyoriy)</Label>
                                        <div className="relative">
                                            <Input 
                                                id="edit-password" 
                                                type={showPasswordEdit ? "text" : "password"} 
                                                value={editingEmployee.password} 
                                                onChange={e => setEditingEmployee({...editingEmployee, password: e.target.value})} 
                                                placeholder="••••••" 
                                                className="pr-10"
                                            />
                                            <Button
                                                type="button"
                                                variant="ghost"
                                                size="icon"
                                                className="absolute right-0 top-0 h-full px-3 text-muted-foreground hover:bg-transparent"
                                                onClick={() => setShowPasswordEdit(!showPasswordEdit)}
                                            >
                                                {showPasswordEdit ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
                                            </Button>
                                        </div>
                                    </div>
                                </div>
                                <div className="grid grid-cols-2 gap-4">
                                    <div className="grid gap-2">
                                        <Label htmlFor="edit-passport">Pasport Seria</Label>
                                        <Input id="edit-passport" value={editingEmployee.passport || ''} onChange={e => setEditingEmployee({...editingEmployee, passport: e.target.value})} required />
                                    </div>
                                    <div className="grid gap-2">
                                        <Label htmlFor="edit-address">Manzil</Label>
                                        <Input id="edit-address" value={editingEmployee.address || ''} onChange={e => setEditingEmployee({...editingEmployee, address: e.target.value})} required />
                                    </div>
                                </div>
                                <div className="grid gap-2">
                                    <Label htmlFor="edit-notes">Qo'himcha izoh</Label>
                                    <Input id="edit-notes" value={editingEmployee.notes || ''} onChange={e => setEditingEmployee({...editingEmployee, notes: e.target.value})} />
                                </div>
                                <div className="grid grid-cols-2 gap-4">
                                    <div className="grid gap-2">
                                        <Label>Lavozim</Label>
                                        <Select 
                                            value={editingEmployee.role} 
                                            onValueChange={(v) => setEditingEmployee({...editingEmployee, role: v})}
                                            disabled={editingEmployee.id === currentUserId || (role === 'manager' && editingEmployee.role !== 'cashier')}
                                        >
                                            <SelectTrigger><SelectValue /></SelectTrigger>
                                            <SelectContent>
                                                <SelectItem value="admin">Admin</SelectItem>
                                                <SelectItem value="manager">Manager</SelectItem>
                                                <SelectItem value="warehouse">Omborchi</SelectItem>
                                                <SelectItem value="cashier">Kassir</SelectItem>
                                            </SelectContent>
                                        </Select>
                                        {editingEmployee.id === currentUserId && (
                                            <span className="text-[10px] text-amber-600 font-medium">O'z rolingizni o'zgartira olmaysiz</span>
                                        )}
                                        {role === 'manager' && editingEmployee.role !== 'cashier' && (
                                            <span className="text-[10px] text-amber-600 font-medium">Faqat kassirlarni boshqara olasiz</span>
                                        )}
                                    </div>
                                    <div className="grid gap-2">
                                        <Label>Status</Label>
                                        <Select 
                                            value={editingEmployee.is_active ? "active" : "blocked"} 
                                            onValueChange={(v) => setEditingEmployee({...editingEmployee, is_active: v === "active"})}
                                            disabled={editingEmployee.id === currentUserId || (role === 'manager' && editingEmployee.role !== 'cashier')}
                                        >
                                            <SelectTrigger><SelectValue /></SelectTrigger>
                                            <SelectContent>
                                                <SelectItem value="active">Aktiv</SelectItem>
                                                <SelectItem value="blocked">Bloklangan</SelectItem>
                                            </SelectContent>
                                        </Select>
                                        {editingEmployee.id === currentUserId && (
                                            <span className="text-[10px] text-amber-600 font-medium">O'zingizni bloklay olmaysiz</span>
                                        )}
                                        {role === 'manager' && editingEmployee.role !== 'cashier' && (
                                            <span className="text-[10px] text-amber-600 font-medium">Faqat kassirlarni bloklay olasiz</span>
                                        )}
                                    </div>
                                </div>
                            </div>
                        )}
                        <DialogFooter>
                            <Button type="submit" disabled={updateEmployeeMutation.isPending}>
                                {updateEmployeeMutation.isPending ? "Saqlanmoqda..." : "Yangilash"}
                            </Button>
                        </DialogFooter>
                    </form>
                </DialogContent>
            </Dialog>

            {/* --- DELETE CONFIRMATION DIALOG --- */}
            <Dialog open={isDeleteConfirmOpen} onOpenChange={setIsDeleteConfirmOpen}>
                <DialogContent className="sm:max-w-[400px]">
                    <DialogHeader>
                        <DialogTitle>Xodimni o'chirish</DialogTitle>
                        <DialogDescription>
                            Haqiqatdan ham <b>{deletingEmployee?.full_name}</b>ni tizimdan o'chirib tashlamoqchimisiz? 
                            Bu amalni ortga qaytarib bo'lmaydi.
                        </DialogDescription>
                    </DialogHeader>
                    <DialogFooter className="gap-2 sm:gap-0">
                        <Button variant="ghost" onClick={() => setIsDeleteConfirmOpen(false)}>Bekor qilish</Button>
                        <Button 
                            variant="destructive" 
                            onClick={() => deleteEmployeeMutation.mutate(deletingEmployee.id)}
                            disabled={deleteEmployeeMutation.isPending}
                        >
                            {deleteEmployeeMutation.isPending ? "O'chirilmoqda..." : "O'chirish"}
                        </Button>
                    </DialogFooter>
                </DialogContent>
            </Dialog>
        </div>
    );
};

export default Employees;
