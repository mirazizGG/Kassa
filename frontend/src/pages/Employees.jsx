import React, { useState } from 'react';
import { useQuery, useMutation } from '@tanstack/react-query';
import api from '../api/axios';
import { queryClient } from '../api/queryClient';
import {
    Users,
    UserPlus,
    CheckSquare,
    Plus,
    Calendar,
    MoreHorizontal
} from 'lucide-react';
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
import { toast } from "sonner";

const Employees = () => {
    const [isTaskModalOpen, setIsTaskModalOpen] = useState(false);
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
             toast.error("Xatolik", { description: err.response?.data?.detail || "Vazifa yaratib bo'lmadi" });
        }
    });

    const handleCreateTask = (e) => {
        e.preventDefault();
        createTaskMutation.mutate({
            ...newTask,
            assigned_to: parseInt(newTask.assigned_to)
        });
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
                <TabsList className="grid w-full grid-cols-2 max-w-[400px]">
                    <TabsTrigger value="list" className="gap-2"><Users className="w-4 h-4"/> Xodimlar</TabsTrigger>
                    <TabsTrigger value="tasks" className="gap-2"><CheckSquare className="w-4 h-4"/> Vazifalar</TabsTrigger>
                </TabsList>

                {/* --- EMPLOYEES LIST CONTENT --- */}
                <TabsContent value="list" className="mt-6">
                    <div className="flex justify-end mb-4">
                         <Button className="gap-2 shadow-lg shadow-primary/20">
                            <UserPlus className="w-4 h-4" /> Yangi Xodim
                        </Button>
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
                                    </TableRow>
                                </TableHeader>
                                <TableBody>
                                    {isEmployeesLoading ? (
                                        <TableRow><TableCell colSpan={5} className="text-center h-24">Yuklanmoqda...</TableCell></TableRow>
                                    ) : employees.map((emp) => (
                                        <TableRow key={emp.id} className="hover:bg-muted/50">
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
                                <Button className="gap-2 shadow-lg shadow-primary/20">
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
            </Tabs>
        </div>
    );
};

export default Employees;
