import React from 'react';
import { AlertCircle, RefreshCcw } from 'lucide-react';
import { Button } from './ui/button';
import { Card, CardContent, CardDescription, CardFooter, CardHeader, CardTitle } from './ui/card';

class ErrorBoundary extends React.Component {
    constructor(props) {
        super(props);
        this.state = { hasError: false, error: null, errorInfo: null };
    }

    static getDerivedStateFromError(error) {
        return { hasError: true };
    }

    componentDidCatch(error, errorInfo) {
        // Log error to console in development
        console.error('Error caught by boundary:', error, errorInfo);

        this.setState({
            error,
            errorInfo
        });

        // You can also log the error to an error reporting service here
        // Example: logErrorToService(error, errorInfo);
    }

    handleReset = () => {
        this.setState({ hasError: false, error: null, errorInfo: null });
        // Optionally reload the page
        window.location.reload();
    };

    render() {
        if (this.state.hasError) {
            return (
                <div className="min-h-screen w-full flex items-center justify-center bg-background p-4">
                    <Card className="w-full max-w-lg border-destructive/50">
                        <CardHeader>
                            <div className="flex items-center gap-3">
                                <div className="p-2 rounded-full bg-destructive/10">
                                    <AlertCircle className="w-6 h-6 text-destructive" />
                                </div>
                                <div>
                                    <CardTitle>Xatolik yuz berdi</CardTitle>
                                    <CardDescription>
                                        Dastur ishida xatolik ro'y berdi
                                    </CardDescription>
                                </div>
                            </div>
                        </CardHeader>
                        <CardContent className="space-y-4">
                            <div className="p-4 rounded-lg bg-muted border">
                                <p className="text-sm font-mono text-muted-foreground">
                                    {this.state.error && this.state.error.toString()}
                                </p>
                            </div>
                            {process.env.NODE_ENV === 'development' && this.state.errorInfo && (
                                <details className="cursor-pointer">
                                    <summary className="text-sm font-medium text-muted-foreground hover:text-foreground">
                                        Texnik ma'lumotlar (Development)
                                    </summary>
                                    <pre className="mt-2 text-xs overflow-auto p-4 bg-muted rounded-lg max-h-48">
                                        {this.state.errorInfo.componentStack}
                                    </pre>
                                </details>
                            )}
                        </CardContent>
                        <CardFooter className="flex gap-3">
                            <Button
                                onClick={this.handleReset}
                                className="flex-1 gap-2"
                            >
                                <RefreshCcw className="w-4 h-4" />
                                Sahifani yangilash
                            </Button>
                            <Button
                                variant="outline"
                                onClick={() => window.location.href = '/'}
                                className="flex-1"
                            >
                                Bosh sahifaga qaytish
                            </Button>
                        </CardFooter>
                    </Card>
                </div>
            );
        }

        return this.props.children;
    }
}

export default ErrorBoundary;
