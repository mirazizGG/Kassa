import React from 'react';
import { useQuery } from '@tanstack/react-query';
import api from '../api/axios';
import {
    Activity,
    User,
    Clock,
    Info,
    AlertTriangle,
    FileText,
    LogIn,
    ShoppingCart,
    Trash2,
    Edit3,
    PlusCircle,
    Package,
    Truck,
    CreditCard,
    Undo2,
    Calendar,
    Settings,
    ChevronRight,
    Search,
    FileDown
} from 'lucide-react';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { format } from "date-fns";
import { Skeleton } from "@/components/ui/skeleton";
import FilterBar from '../components/FilterBar';
import { cn } from "@/lib/utils.js";
import {
    Dialog,
    DialogContent,
    DialogHeader,
    DialogTitle,
    DialogDescription,
} from "@/components/ui/dialog";

const AuditLogs = () => {
    const today = new Date().toISOString().split('T')[0];
    const [selectedLog, setSelectedLog] = React.useState(null);
    const [isExporting, setIsExporting] = React.useState(false);
    const [filters, setFilters] = React.useState({
        employee_id: '',
        action: '',
        search: '',
        start_date: today,
        end_date: today
    });

    const { data: logs = [], isLoading } = useQuery({
        queryKey: ['audit-logs', filters],
        queryFn: async () => {
            const params = {};
            if (filters.employee_id && filters.employee_id !== 'all') params.employee_id = filters.employee_id;
            if (filters.action) params.action = filters.action;
            if (filters.search) params.search = filters.search;
            if (filters.start_date) params.start_date = filters.start_date;
            if (filters.end_date) params.end_date = filters.end_date;

            const res = await api.get('/audit/logs', { params });
            return res.data;
        }
    });

    const handleExport = async () => {
        setIsExporting(true);
        try {
            const params = {};
            if (filters.employee_id && filters.employee_id !== 'all') params.employee_id = filters.employee_id;
            if (filters.action) params.action = filters.action;
            if (filters.search) params.search = filters.search;
            if (filters.start_date) params.start_date = filters.start_date;
            if (filters.end_date) params.end_date = filters.end_date;

            const response = await api.get('/audit/export-excel', {
                params,
                responseType: 'blob'
            });

            const url = window.URL.createObjectURL(new Blob([response.data]));
            const link = document.createElement('a');
            link.href = url;
            link.setAttribute('download', `audit_${format(new Date(), 'yyyyMMdd')}.xlsx`);
            document.body.appendChild(link);
            link.click();
            link.remove();
        } catch (error) {
            console.error('Export error:', error);
        } finally {
            setIsExporting(false);
        }
    };

    const getActionConfig = (action) => {
        const configs = {
            'LOGIN': { icon: LogIn, color: 'bg-blue-500/10 text-blue-600 border-blue-200', label: 'Kirish' },
            'YANGI_SOTUV': { icon: ShoppingCart, color: 'bg-emerald-500/10 text-emerald-600 border-emerald-200', label: 'Sotuv' },
            'VOZVRAT': { icon: Undo2, color: 'bg-rose-500/10 text-rose-600 border-rose-200', label: 'Vozvrat' },
            'YANGI_MAHSULOT': { icon: PlusCircle, color: 'bg-purple-500/10 text-purple-600 border-purple-200', label: 'Yangi Mahsulot' },
            'MAHSULOT_TAHRIR': { icon: Edit3, color: 'bg-amber-500/10 text-amber-600 border-amber-200', label: 'Tahrir' },
            'OMBOR_KIRIM': { icon: Package, color: 'bg-indigo-500/10 text-indigo-600 border-indigo-200', label: 'Ombor Kirimi' },
            'FIRMA_KIRIM': { icon: Truck, color: 'bg-cyan-500/10 text-cyan-600 border-cyan-200', label: 'Firma Kirimi' },
            'FIRMA_TOLOV': { icon: CreditCard, color: 'bg-orange-500/10 text-orange-600 border-orange-200', label: 'Firma To\'lovi' },
            'MIJOZ_TOLOV': { icon: CreditCard, color: 'bg-teal-500/10 text-teal-600 border-teal-200', label: 'Mijoz To\'lovi' },
            'SMENA_OCHILDI': { icon: Calendar, color: 'bg-blue-400/10 text-blue-500 border-blue-200', label: 'Smena Ochiq' },
            'SMENA_YOPILDI': { icon: Calendar, color: 'bg-slate-500/10 text-slate-600 border-slate-200', label: 'Smena Yopiq' },
            'XODIM_OCHIRILDI': { icon: Trash2, color: 'bg-red-500/10 text-red-600 border-red-200', label: 'Xodim O\'chirildi' },
            'SOZLAMALAR_OZGARDI': { icon: Settings, color: 'bg-slate-500/10 text-slate-600 border-slate-200', label: 'Sozlamalar' },
        };
        return configs[action] || { icon: Activity, color: 'bg-gray-500/10 text-gray-600 border-gray-200', label: action };
    };

    return (
        <div className="space-y-6 pb-10">
            {/* Header Section */}
            <div className="flex flex-col gap-6">
                <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
                    <div className="space-y-1">
                        <div className="flex items-center gap-2">
                            <div className="p-2 bg-primary/10 rounded-lg">
                                <Activity className="w-6 h-6 text-primary" />
                            </div>
                            <h1 className="text-3xl font-bold tracking-tight bg-gradient-to-r from-foreground to-foreground/70 bg-clip-text text-transparent">
                                Audit va Nazorat
                            </h1>
                        </div>
                        <p className="text-muted-foreground flex items-center gap-2">
                            <Info className="w-4 h-4" />
                            Tizimdagi barcha muhim amallar va o'zgarishlar tarixi (Real vaqt rejimida)
                        </p>
                    </div>

                    <Button 
                        onClick={handleExport}
                        disabled={isExporting}
                        variant="outline" 
                        className="bg-background hover:bg-muted border-primary/20 text-primary gap-2"
                    >
                        {isExporting ? (
                            <div className="w-4 h-4 border-2 border-primary/30 border-t-primary rounded-full animate-spin" />
                        ) : (
                            <FileDown className="w-4 h-4" />
                        )}
                        Excelga yuklash
                    </Button>
                </div>
                
                <FilterBar filters={filters} onFilterChange={setFilters} showActionFilter={true} />
            </div>

            {/* Main Content Card */}
            <Card className="border-none shadow-2xl overflow-hidden bg-background/40 backdrop-blur-2xl ring-1 ring-border/50">
                <CardHeader className="border-b bg-muted/20 pb-4">
                    <div className="flex items-center justify-between">
                        <div className="space-y-1">
                            <CardTitle className="text-lg flex items-center gap-2">
                                <FileText className="w-4 h-4 text-primary" />
                                Tizim jurnali
                            </CardTitle>
                            <CardDescription>Oxirgi bajarilgan amallar ro'yxati</CardDescription>
                        </div>
                        <div className="px-3 py-1 bg-primary/10 text-primary text-[10px] font-bold uppercase rounded-full tracking-wider border border-primary/20">
                            {logs.length} ta yozuv topildi
                        </div>
                    </div>
                </CardHeader>
                <CardContent className="p-0">
                    <div className="overflow-x-auto">
                        <Table>
                            <TableHeader className="bg-muted/10">
                                <TableRow className="hover:bg-transparent border-none">
                                    <TableHead className="w-[200px] pl-6 h-12">Mas'ul xodim</TableHead>
                                    <TableHead className="w-[180px] h-12">Amal turi</TableHead>
                                    <TableHead className="min-w-[300px] h-12">Batafsil ma'lumot</TableHead>
                                    <TableHead className="w-[180px] h-12">Vaqti</TableHead>
                                    <TableHead className="w-[50px]"></TableHead>
                                </TableRow>
                            </TableHeader>
                            <TableBody>
                                {isLoading ? (
                                    Array.from({ length: 8 }).map((_, i) => (
                                        <TableRow key={i} className="border-b/50">
                                            <TableCell className="pl-6"><Skeleton className="h-10 w-32 rounded-lg" /></TableCell>
                                            <TableCell><Skeleton className="h-6 w-24 rounded-full" /></TableCell>
                                            <TableCell><Skeleton className="h-4 w-full rounded-md" /></TableCell>
                                            <TableCell className="pr-6"><Skeleton className="h-4 w-24 rounded-md" /></TableCell>
                                            <TableCell></TableCell>
                                        </TableRow>
                                    ))
                                ) : logs.length === 0 ? (
                                    <TableRow>
                                        <TableCell colSpan={5} className="h-64 text-center">
                                            <div className="flex flex-col items-center justify-center space-y-3 opacity-50">
                                                <div className="p-4 bg-muted rounded-full">
                                                    <AlertTriangle className="w-8 h-8" />
                                                </div>
                                                <p className="text-xl font-medium">Hech qanday ma'lumot topilmadi</p>
                                                <p className="text-sm">Filtrlarni o'zgartirib ko'ring</p>
                                            </div>
                                        </TableCell>
                                    </TableRow>
                                ) : logs.map((log) => {
                                    const config = getActionConfig(log.action);
                                    const Icon = config.icon;
                                    
                                    return (
                                        <TableRow 
                                            key={log.id} 
                                            onClick={() => setSelectedLog(log)}
                                            className="group cursor-pointer hover:bg-primary/5 transition-all duration-300 border-b/50"
                                        >
                                            <TableCell className="pl-6 py-4">
                                                <div className="flex items-center gap-3">
                                                    <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-secondary to-muted flex items-center justify-center ring-2 ring-background shadow-sm group-hover:scale-110 transition-transform">
                                                        <User className="w-5 h-5 text-muted-foreground" />
                                                    </div>
                                                    <div className="flex flex-col">
                                                        <span className="text-sm font-bold tracking-tight leading-none mb-1">
                                                            {log.user?.full_name || log.user?.username}
                                                        </span>
                                                        <span className="text-[10px] text-muted-foreground font-medium uppercase tracking-wider flex items-center gap-1">
                                                            <div className={cn("w-1.5 h-1.5 rounded-full", 
                                                                log.user?.role === 'admin' ? 'bg-red-500' : 'bg-blue-500'
                                                            )} />
                                                            {log.user?.role}
                                                        </span>
                                                    </div>
                                                </div>
                                            </TableCell>
                                            <TableCell className="py-4">
                                                <Badge 
                                                    variant="secondary" 
                                                    className={cn(
                                                        "h-7 px-3 text-[11px] font-bold rounded-lg border flex items-center gap-1.5 w-fit",
                                                        config.color
                                                    )}
                                                >
                                                    <Icon className="w-3.5 h-3.5" />
                                                    {config.label}
                                                </Badge>
                                            </TableCell>
                                            <TableCell className="py-4">
                                                <div className="max-w-[450px]">
                                                    <p className="text-sm text-foreground/80 font-medium leading-relaxed italic truncate">
                                                        "{log.details}"
                                                    </p>
                                                </div>
                                            </TableCell>
                                            <TableCell className="py-4 text-right pr-6 md:text-left md:pr-0">
                                                <div className="flex flex-col gap-1">
                                                    <div className="flex items-center gap-1.5 text-xs font-bold text-muted-foreground">
                                                        <Calendar className="w-3.5 h-3.5" />
                                                        {format(new Date(log.created_at), 'dd.MM.yyyy')}
                                                    </div>
                                                    <div className="flex items-center gap-1.5 text-[11px] font-medium text-primary/60">
                                                        <Clock className="w-3.5 h-3.5" />
                                                        {format(new Date(log.created_at), 'HH:mm:ss')}
                                                    </div>
                                                </div>
                                            </TableCell>
                                            <TableCell className="py-4 pr-6 opacity-0 group-hover:opacity-100 transition-opacity">
                                                <ChevronRight className="w-5 h-5 text-primary" />
                                            </TableCell>
                                        </TableRow>
                                    );
                                })}
                            </TableBody>
                        </Table>
                    </div>
                </CardContent>
            </Card>

            {/* Details Modal */}
            <Dialog open={!!selectedLog} onOpenChange={(open) => !open && setSelectedLog(null)}>
                <DialogContent className="sm:max-w-[500px] p-0 overflow-hidden bg-background/90 backdrop-blur-2xl border-primary/20 shadow-2xl">
                    <DialogHeader className="p-6 bg-primary/5 border-b border-primary/10">
                        <div className="flex items-center gap-4">
                            <div className={cn("p-3 rounded-2xl border", selectedLog ? getActionConfig(selectedLog.action).color : "")}>
                                {selectedLog && React.createElement(getActionConfig(selectedLog.action).icon, { className: "w-6 h-6" })}
                            </div>
                            <div>
                                <DialogTitle className="text-xl font-bold tracking-tight">
                                    Amal tafsilotlari
                                </DialogTitle>
                                <DialogDescription className="text-xs uppercase tracking-[0.1em] font-bold opacity-70">
                                    ID: #{selectedLog?.id}
                                </DialogDescription>
                            </div>
                        </div>
                    </DialogHeader>
                    
                    <div className="p-6 space-y-6">
                        {/* Meta Grid */}
                        <div className="grid grid-cols-2 gap-4">
                            <div className="space-y-1.5 p-3 rounded-xl bg-muted/30 border border-border/50">
                                <span className="text-[10px] font-bold text-muted-foreground uppercase flex items-center gap-1">
                                    <User className="w-3 h-3" /> Mas'ul xodim
                                </span>
                                <p className="text-sm font-bold">{selectedLog?.user?.full_name || selectedLog?.user?.username}</p>
                            </div>
                            <div className="space-y-1.5 p-3 rounded-xl bg-muted/30 border border-border/50">
                                <span className="text-[10px] font-bold text-muted-foreground uppercase flex items-center gap-1">
                                    <Clock className="w-3 h-3" /> Vaqti
                                </span>
                                <p className="text-sm font-bold">
                                    {selectedLog && format(new Date(selectedLog.created_at), 'dd.MM.yyyy HH:mm:ss')}
                                </p>
                            </div>
                        </div>

                        {/* Action Type */}
                        <div className="space-y-2">
                             <span className="text-[10px] font-bold text-muted-foreground uppercase tracking-wider">
                                Amal turi
                            </span>
                            <div className={cn(
                                "p-4 rounded-xl border flex items-center justify-between",
                                selectedLog ? getActionConfig(selectedLog.action).color : ""
                            )}>
                                <span className="font-bold">{selectedLog && getActionConfig(selectedLog.action).label}</span>
                                <Badge variant="outline" className="text-[10px] border-current opacity-70">Muvaffaqiyatli</Badge>
                            </div>
                        </div>

                        {/* Description */}
                        <div className="space-y-2">
                            <span className="text-[10px] font-bold text-muted-foreground uppercase tracking-wider">
                                Batafsil bayonot
                            </span>
                            <div className="p-4 rounded-xl bg-muted/20 border border-border/50 min-h-[100px]">
                                <p className="text-sm leading-relaxed font-medium italic text-foreground/90">
                                    "{selectedLog?.details}"
                                </p>
                            </div>
                        </div>
                    </div>

                    <div className="p-4 bg-muted/10 border-t border-border/50 text-center">
                        <p className="text-[10px] text-muted-foreground font-medium">
                            Ushbu amal tizim tomonidan avtomatik qayd etilgan va o'zgartirib bo'lmaydi.
                        </p>
                    </div>
                </DialogContent>
            </Dialog>
        </div>
    );
};

export default AuditLogs;
