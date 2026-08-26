import React from 'react';
import { AlertCircle, RefreshCcw, Home } from 'lucide-react';
import { Button } from './ui/button';
import { Card, CardContent, CardDescription, CardFooter, CardHeader, CardTitle } from './ui/card';
import { useNavigate } from 'react-router-dom';

export const ErrorDisplay = ({
    error,
    title = "Xatolik yuz berdi",
    description = "Ma'lumotlarni yuklashda xatolik yuz berdi",
    onRetry,
    showHomeButton = false
}) => {
    const navigate = useNavigate();

    return (
        <Card className="border-destructive/50 max-w-lg mx-auto my-8">
            <CardHeader>
                <div className="flex items-center gap-3">
                    <div className="p-2 rounded-full bg-destructive/10">
                        <AlertCircle className="w-5 h-5 text-destructive" />
                    </div>
                    <div>
                        <CardTitle className="text-lg">{title}</CardTitle>
                        <CardDescription>{description}</CardDescription>
                    </div>
                </div>
            </CardHeader>
            {error && (
                <CardContent>
                    <div className="p-3 rounded-lg bg-muted border text-sm">
                        <p className="text-muted-foreground">
                            {error.response?.data?.detail || error.message || "Noma'lum xatolik"}
                        </p>
                    </div>
                </CardContent>
            )}
            <CardFooter className="flex gap-2">
                {onRetry && (
                    <Button onClick={onRetry} className="gap-2 flex-1">
                        <RefreshCcw className="w-4 h-4" />
                        Qayta urinish
                    </Button>
                )}
                {showHomeButton && (
                    <Button variant="outline" onClick={() => navigate('/')} className="gap-2 flex-1">
                        <Home className="w-4 h-4" />
                        Bosh sahifa
                    </Button>
                )}
            </CardFooter>
        </Card>
    );
};

export const InlineError = ({ message, className }) => {
    return (
        <div className={`flex items-center gap-2 p-3 rounded-lg bg-destructive/10 text-destructive text-sm ${className}`}>
            <AlertCircle className="w-4 h-4 flex-shrink-0" />
            <span>{message}</span>
        </div>
    );
};

export default ErrorDisplay;
