import { cn } from "@/lib/utils";
import { LucideIcon } from "lucide-react";

interface MetricCardProps {
  title: string;
  value: string | number;
  icon?: LucideIcon;
  variant?: 'warning' | 'coral' | 'info' | 'success' | 'default';
  className?: string;
}

export const MetricCard = ({ 
  title, 
  value, 
  icon: Icon, 
  variant = 'default',
  className 
}: MetricCardProps) => {
  const variantClasses = {
    warning: 'bg-warning text-warning-foreground',
    coral: 'bg-coral text-coral-foreground',
    info: 'bg-info text-info-foreground',
    success: 'bg-success text-success-foreground',
    default: 'bg-card text-card-foreground border border-border'
  };

  return (
    <div
      className={cn(
        "rounded-2xl p-6 transition-all duration-200",
        "hover:shadow-lg",
        variantClasses[variant],
        className
      )}
    >
      <div className="flex items-start justify-between">
        <div className="flex-1">
          <h3 className="text-sm font-medium mb-2 opacity-90">{title}</h3>
          <p className="text-3xl font-bold">{value}</p>
        </div>
        {Icon && (
          <div className="ml-4">
            <Icon className="w-8 h-8 opacity-70" />
          </div>
        )}
      </div>
    </div>
  );
};
