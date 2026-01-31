
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
import { Users, Calendar, X } from 'lucide-react';

const FilterBar = ({ filters, onFilterChange }) => {
    const { data: employees } = useQuery({
        queryKey: ['employees'],
        queryFn: async () => {
            const response = await api.get('/auth/employees');
            return response.data;
        }
    });

    const handleClear = () => {
        const today = new Date().toISOString().split('T')[0];
        onFilterChange({
            employee_id: '',
            start_date: today,
            end_date: today
        });
    };

    const hasFilters = filters.employee_id || filters.start_date || filters.end_date;

    return (
        <div className="flex flex-wrap items-center gap-4 bg-card p-4 rounded-xl border shadow-sm">
            <div className="flex items-center gap-2 min-w-[200px]">
                <Users className="h-4 w-4 text-muted-foreground" />
                <Select 
                    value={filters.employee_id?.toString()} 
                    onValueChange={(val) => onFilterChange({ ...filters, employee_id: val })}
                >
                    <SelectTrigger className="w-full">
                        <SelectValue placeholder="Barcha xodimlar" />
                    </SelectTrigger>
                    <SelectContent>
                        <SelectItem value="all">Barcha xodimlar</SelectItem>
                        {employees?.map((emp) => (
                            <SelectItem key={emp.id} value={emp.id.toString()}>
                                {emp.full_name || emp.username} ({emp.role})
                            </SelectItem>
                        ))}
                    </SelectContent>
                </Select>
            </div>

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
                    className="h-9 px-2 text-muted-foreground hover:text-foreground"
                >
                    <X className="h-4 w-4 mr-1" />
                    Tozalash
                </Button>
            )}
        </div>
    );
};

export default FilterBar;
