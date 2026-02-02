import * as React from "react"
import { Slot } from "@radix-ui/react-slot"
import { cva } from "class-variance-authority";

import { cn } from "@/lib/utils"

const buttonVariants = cva(
  "inline-flex items-center justify-center gap-2 whitespace-nowrap rounded-md text-sm font-medium transition-colors focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring disabled:pointer-events-none disabled:opacity-50 [&_svg]:pointer-events-none [&_svg]:size-4 [&_svg]:shrink-0",
  {
    variants: {
      variant: {
        default:
          "bg-gradient-to-r from-blue-600 to-indigo-600 text-primary-foreground shadow-lg shadow-blue-500/30 hover:shadow-blue-500/50 hover:scale-[1.02] active:scale-95 transition-all duration-300 border-0",
        destructive:
          "bg-gradient-to-r from-red-500 to-rose-600 text-destructive-foreground shadow-lg shadow-red-500/30 hover:shadow-red-500/50 hover:scale-[1.02] active:scale-95 transition-all duration-300",
        outline:
          "border border-input bg-background shadow-sm hover:bg-accent hover:text-accent-foreground hover:scale-[1.02] active:scale-95 transition-all duration-200",
        secondary:
          "bg-secondary text-secondary-foreground shadow-sm hover:bg-secondary/80 hover:scale-[1.02] active:scale-95 transition-all duration-200",
        ghost: "hover:bg-accent hover:text-accent-foreground hover:scale-105 transition-all duration-200",
        link: "text-primary underline-offset-4 hover:underline",
        success: 
          "bg-gradient-to-r from-emerald-500 to-green-600 text-white shadow-lg shadow-emerald-500/30 hover:shadow-emerald-500/50 hover:scale-[1.02] active:scale-95 transition-all duration-300 border-0",
        warning: 
          "bg-gradient-to-r from-amber-500 to-orange-500 text-white shadow-lg shadow-orange-500/30 hover:shadow-orange-500/50 hover:scale-[1.02] active:scale-95 transition-all duration-300 border-0",
        info: 
          "bg-gradient-to-r from-sky-500 to-blue-500 text-white shadow-lg shadow-blue-400/30 hover:shadow-blue-400/50 hover:scale-[1.02] active:scale-95 transition-all duration-300 border-0",
        indigo: 
          "bg-gradient-to-r from-violet-600 to-indigo-600 text-white shadow-lg shadow-indigo-500/30 hover:shadow-indigo-500/50 hover:scale-[1.02] active:scale-95 transition-all duration-300 border-0",
      },
      size: {
        default: "h-9 px-4 py-2",
        sm: "h-8 rounded-md px-3 text-xs",
        lg: "h-10 rounded-md px-8",
        icon: "h-9 w-9",
      },
    },
    defaultVariants: {
      variant: "default",
      size: "default",
    },
  }
)

const Button = React.forwardRef(({ className, variant, size, asChild = false, ...props }, ref) => {
  const Comp = asChild ? Slot : "button"
  return (
    <Comp
      className={cn(buttonVariants({ variant, size, className }))}
      ref={ref}
      {...props} />
  );
})
Button.displayName = "Button"

export { Button, buttonVariants }
