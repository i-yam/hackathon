import { Button } from "@/components/ui/button";
import { Filter } from "lucide-react";
import { cn } from "@/lib/utils";

interface FilterControlsProps {
  activeFilter: 'all' | 'high' | 'low';
  onFilterChange: (filter: 'all' | 'high' | 'low') => void;
}

export const FilterControls = ({ activeFilter, onFilterChange }: FilterControlsProps) => {
  return (
    <div className="flex items-center gap-3">
      <div className="flex items-center gap-2 text-sm font-medium text-foreground">
        <Filter className="w-4 h-4" />
        Filter
      </div>
      
      <Button
        variant="outline"
        size="sm"
        onClick={() => onFilterChange('high')}
        className={cn(
          "rounded-lg transition-all duration-200 border-2",
          activeFilter === 'high'
            ? "bg-warning text-warning-foreground border-warning shadow-md"
            : "border-border hover:border-warning/50"
        )}
      >
        higher risk
      </Button>
      
      <Button
        variant="outline"
        size="sm"
        onClick={() => onFilterChange('low')}
        className={cn(
          "rounded-lg transition-all duration-200 border-2",
          activeFilter === 'low'
            ? "bg-success text-success-foreground border-success shadow-md"
            : "border-border hover:border-success/50"
        )}
      >
        lower risk
      </Button>
    </div>
  );
};
