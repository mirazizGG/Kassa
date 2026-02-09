
import React from 'react';
import { useQuery } from '@tanstack/react-query';
import api from '../api/axios';
import { 
    Clock, 
    Calendar, 
    User, 
    ArrowRightCircle, 
    ArrowLeftCircle,
    Info,
    History
} from 'lucide-react';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Badge } from "@/components/ui/badge";
import { format } from "date-fns";
import { Skeleton } from "@/components/ui/skeleton";
import FilterBar from '../components/FilterBar';

const Attendance = () => {
    const today = new Date().toISOString().split('T')[0];
    const [filters, setFilters] = React.useState({
        employee_id: '',
        start_date: today,
        end_date: today
    });

    const { data: logs = [], isLoading } = useQuery({
        queryKey: ['attendance-logs', filters],
        queryFn: async () => {
            const params = {};
            if (filters.employee_id && filters.employee_id !== 'all') params.employee_id = filters.employee_id;
            if (filters.start_date) params.start_date = filters.start_date;
            if (filters.end_date) params.end_date = filters.end_date;

            const res = await api.get('/auth/attendance', { params });
            return res.data;
        }
    });

    return (
        <div className="space-y-6 pb-10">
            <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
                <div className="space-y-1">
                    <div className="flex items-center gap-2">
                        <div className="p-2 bg-primary/10 rounded-lg">
                            <Clock className="w-6 h-6 text-primary" />
                        </div>
                        <h1 className="text-3xl font-bold tracking-tight">Xodimlar Davomati</h1>
                    </div>
                    <p className="text-muted-foreground flex items-center gap-2">
                        <Info className="w-4 h-4" />
                        Telegram bot orqali kelib-ketish vaqtlarini nazorat qilish
                    </p>
                </div>
            </div>

            <FilterBar filters={filters} onFilterChange={setFilters} />

            <Card className="border-none shadow-md overflow-hidden bg-background/60 backdrop-blur-xl">
                <CardHeader className="bg-muted/30">
                    <CardTitle className="text-lg flex items-center gap-2">
                        <History className="w-5 h-5 text-primary" />
                        Davomat Jurnali
                    </CardTitle>
                    <CardDescription>Xodimlarning tizimdagi oxirgi harakatlari</CardDescription>
                </CardHeader>
                <CardContent className="p-0">
                    <Table>
                        <TableHeader>
                            <TableRow className="hover:bg-transparent">
                                <TableHead className="w-[200px] pl-6">Xodim</TableHead>
                                <TableHead>Status</TableHead>
                                <TableHead>Sana</TableHead>
                                <TableHead>Vaqt</TableHead>
                                <TableHead className="pr-6">Izoh</TableHead>
                            </TableRow>
                        </TableHeader>
                        <TableBody>
                            {isLoading ? (
                                Array.from({ length: 5 }).map((_, i) => (
                                    <TableRow key={i}>
                                        <TableCell colSpan={5} className="py-8">
                                            <div className="flex items-center gap-4 px-4">
                                                <Skeleton className="h-10 w-10 rounded-full" />
                                                <div className="space-y-2">
                                                    <Skeleton className="h-4 w-32" />
                                                    <Skeleton className="h-3 w-24" />
                                                </div>
                                            </div>
                                        </TableCell>
                                    </TableRow>
                                ))
                            ) : logs.length === 0 ? (
                                <TableRow>
                                    <TableCell colSpan={5} className="h-64 text-center">
                                        <div className="flex flex-col items-center justify-center opacity-40">
                                            <Calendar className="w-16 h-16 mb-4" />
                                            <p className="text-lg font-medium">Bu davr uchun ma'lumot topilmadi</p>
                                        </div>
                                    </TableCell>
                                </TableRow>
                            ) : (
                                logs.map((log) => (
                                    <TableRow key={log.id} className="group transition-colors duration-200">
                                        <TableCell className="pl-6 font-medium">
                                            <div className="flex items-center gap-3">
                                                <div className="w-8 h-8 rounded-full bg-primary/10 flex items-center justify-center text-primary text-xs">
                                                    {log.employee?.username?.charAt(0).toUpperCase() || 'U'}
                                                </div>
                                                <span>{log.employee?.username || "Noma'lum"}</span>
                                            </div>
                                        </TableCell>
                                        <TableCell>
                                            {log.status === 'in' ? (
                                                <Badge className="bg-emerald-500/10 text-emerald-600 hover:bg-emerald-500/20 border-emerald-200 flex w-fit items-center gap-1.5 px-3 py-1">
                                                    <ArrowRightCircle className="w-4 h-4" />
                                                    Ishga keldi
                                                </Badge>
                                            ) : (
                                                <Badge className="bg-orange-500/10 text-orange-600 hover:bg-orange-500/20 border-orange-200 flex w-fit items-center gap-1.5 px-3 py-1">
                                                    <ArrowLeftCircle className="w-4 h-4" />
                                                    Ishdan ketdi
                                                </Badge>
                                            )}
                                        </TableCell>
                                        <TableCell className="text-muted-foreground font-medium">
                                            {format(new Date(log.created_at), 'dd.MM.yyyy')}
                                        </TableCell>
                                        <TableCell className="font-bold text-foreground">
                                            {format(new Date(log.created_at), 'HH:mm')}
                                        </TableCell>
                                        <TableCell className="pr-6 italic text-muted-foreground">
                                            {log.note || '-'}
                                        </TableCell>
                                    </TableRow>
                                ))
                            )}
                        </TableBody>
                    </Table>
                </CardContent>
            </Card>
        </div>
    );
};

export default Attendance;
