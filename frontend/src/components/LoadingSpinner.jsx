import React from 'react';
import { Loader2 } from 'lucide-react';
import { cn } from '@/lib/utils.js';

export const LoadingSpinner = ({ size = 'default', className, fullScreen = false }) => {
    const sizeClasses = {
        sm: 'w-4 h-4',
        default: 'w-8 h-8',
        lg: 'w-12 h-12',
        xl: 'w-16 h-16'
    };

    if (fullScreen) {
        return (
            <div className="min-h-[400px] w-full flex items-center justify-center">
                <Loader2 className={cn('animate-spin text-primary', sizeClasses[size], className)} />
            </div>
        );
    }

    return (
        <Loader2 className={cn('animate-spin text-primary', sizeClasses[size], className)} />
    );
};

export const LoadingSkeleton = ({ rows = 5 }) => {
    return (
        <div className="space-y-3">
            {Array.from({ length: rows }).map((_, i) => (
                <div key={i} className="h-12 bg-muted animate-pulse rounded-lg" />
            ))}
        </div>
    );
};

export default LoadingSpinner;
