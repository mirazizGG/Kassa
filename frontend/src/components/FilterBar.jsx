
import React from 'react';
import { useQuery } from '@tanstack/react-query';
import api from '../api/axios';
import {
    Select,
    SelectContent,
    SelectItem,
    SelectTrigger,
    SelectValue,
} from "@/components/ui/select";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Users, Calendar, X, Search, Activity } from 'lucide-react';

const FilterBar = ({ filters, onFilterChange, showActionFilter = false }) => {
    const { data: employees } = useQuery({
        queryKey: ['employees'],
        queryFn: async () => {
            const response = await api.get('/auth/employees');
            return response.data;
        }
    });

    const ACTIONS = [
        { value: 'LOGIN', label: 'Tizimga kirish' },
        { value: 'YANGI_SOTUV', label: 'Sotuv' },
        { value: 'YANGI_MAHSULOT', label: 'Yangi mahsulot' },
        { value: 'OMBOR_KIRIM', label: 'Ombor kirimi' },
        { value: 'FIRMA_KIRIM', label: 'Firma kirimi' },
        { value: 'FIRMA_TOLOV', label: 'Firma to\'lovi' },
        { value: 'MIJOZ_TOLOV', label: 'Mijoz to\'lovi' },
        { value: 'VOZVRAT', label: 'Vozvrat' },
        { value: 'SMENA_OCHILDI', label: 'Smena ochilishi' },
        { value: 'SMENA_YOPILDI', label: 'Smena yopilishi' },
    ];

    const handleClear = () => {
        const today = new Date().toISOString().split('T')[0];
        onFilterChange({
            employee_id: '',
            action: '',
            search: '',
            start_date: today,
            end_date: today
        });
    };

    const hasFilters = filters.employee_id || filters.start_date || filters.end_date || filters.action || filters.search;

    return (
        <div className="flex flex-wrap items-center gap-4 bg-card p-4 rounded-xl border shadow-sm">
            <div className="flex items-center gap-2 relative min-w-[200px]">
                <Search className="h-4 w-4 absolute left-3 text-muted-foreground" />
                <Input 
                    placeholder="Qidirish..." 
                    className="pl-9 h-9"
                    value={filters.search || ''}
                    onChange={(e) => onFilterChange({ ...filters, search: e.target.value })}
                />
            </div>

            <div className="flex items-center gap-2 min-w-[180px]">
                <Users className="h-4 w-4 text-muted-foreground" />
                <Select 
                    value={filters.employee_id?.toString() || 'all'} 
                    onValueChange={(val) => onFilterChange({ ...filters, employee_id: val === 'all' ? '' : val })}
                >
                    <SelectTrigger className="h-9">
                        <SelectValue placeholder="Xodim" />
                    </SelectTrigger>
                    <SelectContent>
                        <SelectItem value="all">Barcha xodimlar</SelectItem>
                        {employees?.map((emp) => (
                            <SelectItem key={emp.id} value={emp.id.toString()}>
                                {emp.full_name || emp.username}
                            </SelectItem>
                        ))}
                    </SelectContent>
                </Select>
            </div>

            {showActionFilter && (
                <div className="flex items-center gap-2 min-w-[180px]">
                    <Activity className="h-4 w-4 text-muted-foreground" />
                    <Select 
                        value={filters.action || 'all'} 
                        onValueChange={(val) => onFilterChange({ ...filters, action: val === 'all' ? '' : val })}
                    >
                        <SelectTrigger className="h-9">
                            <SelectValue placeholder="Amal turi" />
                        </SelectTrigger>
                        <SelectContent>
                            <SelectItem value="all">Barcha amallar</SelectItem>
                            {ACTIONS.map((act) => (
                                <SelectItem key={act.value} value={act.value}>{act.label}</SelectItem>
                            ))}
                        </SelectContent>
                    </Select>
                </div>
            )}

            <div className="flex items-center gap-2">
                <Calendar className="h-4 w-4 text-muted-foreground" />
                <div className="flex items-center gap-1">
                    <Input 
                        type="date" 
                        className="w-auto h-9 text-sm" 
                        value={filters.start_date}
                        onChange={(e) => onFilterChange({ ...filters, start_date: e.target.value })}
                    />
                    <span className="text-muted-foreground">-</span>
                    <Input 
                        type="date" 
                        className="w-auto h-9 text-sm" 
                        value={filters.end_date}
                        onChange={(e) => onFilterChange({ ...filters, end_date: e.target.value })}
                    />
                </div>
            </div>

            {hasFilters && (
                <Button 
                    variant="ghost" 
                    size="sm" 
                    onClick={handleClear}
                    className="h-9 px-2 text-muted-foreground hover:text-foreground ml-auto"
                >
                    <X className="h-4 w-4 mr-1" />
                    Tozalash
                </Button>
            )}
        </div>
    );
};

export default FilterBar;
