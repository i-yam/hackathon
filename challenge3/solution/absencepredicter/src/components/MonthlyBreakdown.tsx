import { MonthlyData } from "@/data/mockData";
import { cn } from "@/lib/utils";

interface MonthlyBreakdownProps {
  data?: MonthlyData[];
}

export const MonthlyBreakdown = ({ data }: MonthlyBreakdownProps) => {
  if (!data || data.length === 0) {
    return null;
  }

  const getColorClass = (days: number) => {
    if (days === 0) return 'bg-muted text-muted-foreground';
    if (days <= 3) return 'bg-success/20 text-success-foreground';
    if (days <= 5) return 'bg-warning/20 text-warning-foreground';
    if (days <= 7) return 'bg-coral/30 text-coral-foreground';
    return 'bg-danger/20 text-danger-foreground';
  };

  return (
    <div className="bg-card rounded-2xl p-6 border border-border">
      <h3 className="text-lg font-semibold mb-4">Monthly breakdown</h3>
      <div className="space-y-2">
        {data.map((month) => (
          <div
            key={month.month}
            className="flex items-center justify-between p-3 rounded-lg bg-muted/30"
          >
            <span className="text-sm font-medium">{month.month}</span>
            <div
              className={cn(
                "px-4 py-1 rounded-lg text-sm font-semibold min-w-[80px] text-center",
                getColorClass(month.days)
              )}
            >
              {month.days} {month.days === 1 ? 'day' : 'days'}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
};
