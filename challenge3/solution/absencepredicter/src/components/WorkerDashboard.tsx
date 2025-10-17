import { WorkerData } from "@/data/mockData";
import { MetricCard } from "./MetricCard";
import { SicknessChart } from "./SicknessChart";
import { MonthlyBreakdown } from "./MonthlyBreakdown";
import { Calendar, TrendingUp, AlertCircle, Activity } from "lucide-react";
import { Badge } from "@/components/ui/badge";

interface WorkerDashboardProps {
  worker: WorkerData;
}

export const WorkerDashboard = ({ worker }: WorkerDashboardProps) => {
  const latestYear = worker.yearlyData[worker.yearlyData.length - 1];
  
  return (
    <div className="space-y-6">
      {/* Header with worker info */}
      <div className="bg-card rounded-2xl p-6 border border-border">
        <div className="flex items-start justify-between">
          <div>
            <h1 className="text-3xl font-bold mb-2">{worker.name}</h1>
            <div className="flex items-center gap-4 text-sm text-muted-foreground">
              <span>{worker.jobType}</span>
              <span>•</span>
              <span>Started: {new Date(worker.startDate).toLocaleDateString()}</span>
            </div>
          </div>
          <Badge
            variant={worker.riskLevel === 'high' ? 'destructive' : 'default'}
            className={
              worker.riskLevel === 'high'
                ? 'bg-danger text-danger-foreground'
                : 'bg-success text-success-foreground'
            }
          >
            {worker.riskLevel === 'high' ? 'Higher Risk' : 'Lower Risk'}
          </Badge>
        </div>
      </div>

      {/* Key Metrics */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
        <MetricCard
          title="Person's average of sickness days"
          value={worker.averageSickDays.toFixed(1)}
          icon={Calendar}
          variant="warning"
        />
        
        <MetricCard
          title="Frequency of sickness per year"
          value={worker.frequencyPerYear.toFixed(1)}
          icon={TrendingUp}
          variant="info"
        />
        
        <MetricCard
          title="Days of sickness per year"
          value={latestYear?.daysSickness || 0}
          icon={Activity}
          variant="coral"
        />
      </div>

      {/* Chart */}
      <SicknessChart data={worker.yearlyData} />

      {/* Monthly Breakdown */}
      {latestYear?.monthlyBreakdown && (
        <MonthlyBreakdown data={latestYear.monthlyBreakdown} />
      )}

      {/* Status Information */}
      <div className="bg-warning/10 rounded-2xl p-6 border-2 border-warning">
        <div className="flex items-start gap-3">
          <AlertCircle className="w-6 h-6 text-warning-foreground mt-1" />
          <div>
            <h3 className="text-lg font-semibold text-warning-foreground mb-2">
              The Person has:
            </h3>
            <div className="space-y-2">
              <div className="flex items-center gap-2">
                <span className="text-warning-foreground font-medium">
                  Dauer-Krank Status:
                </span>
                <Badge variant={worker.isDauerKrank ? 'destructive' : 'default'}>
                  {worker.isDauerKrank ? 'Yes' : 'No'}
                </Badge>
              </div>
              <p className="text-sm text-warning-foreground/80">
                Average sickness frequency: {worker.frequencyPerYear.toFixed(1)} times per year
              </p>
              <p className="text-sm text-warning-foreground/80">
                Total employment duration: {new Date().getFullYear() - new Date(worker.startDate).getFullYear()} years
              </p>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};
