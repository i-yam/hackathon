import { WorkerData } from "@/data/mockData";
import { UserCircle, Activity } from "lucide-react";
import { cn } from "@/lib/utils";
import { ScrollArea } from "@/components/ui/scroll-area";

interface UserSidebarProps {
  workers: WorkerData[];
  selectedWorker: WorkerData | null;
  onSelectWorker: (worker: WorkerData) => void;
}

export const UserSidebar = ({ workers, selectedWorker, onSelectWorker }: UserSidebarProps) => {
  return (
    <div className="w-72 border-r border-border bg-card flex flex-col h-full">
      <div className="p-6 border-b border-border">
        <h2 className="text-lg font-semibold flex items-center gap-2">
          <UserCircle className="w-5 h-5 text-primary" />
          Workers
        </h2>
      </div>
      
      <ScrollArea className="flex-1">
        <div className="p-4 space-y-2">
          {workers.map((worker) => (
            <button
              key={worker.workerId}
              onClick={() => onSelectWorker(worker)}
              className={cn(
                "w-full flex items-center gap-3 p-4 rounded-xl transition-all duration-200",
                "hover:shadow-md border",
                selectedWorker?.workerId === worker.workerId
                  ? "bg-primary/10 border-primary shadow-md"
                  : "bg-background border-border hover:border-primary/50"
              )}
            >
              <div
                className={cn(
                  "w-12 h-12 rounded-full flex items-center justify-center",
                  worker.riskLevel === 'high' 
                    ? "bg-danger/20" 
                    : "bg-success/20"
                )}
              >
                <Activity
                  className={cn(
                    "w-6 h-6",
                    worker.riskLevel === 'high' ? "text-danger" : "text-success"
                  )}
                />
              </div>
              <div className="flex-1 text-left">
                <div className="font-semibold text-sm">{worker.name}</div>
                <div className="text-xs text-muted-foreground">{worker.jobType}</div>
              </div>
            </button>
          ))}
        </div>
      </ScrollArea>
    </div>
  );
};
