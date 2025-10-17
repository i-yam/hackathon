import { useState, useMemo } from "react";
import { mockWorkers, WorkerData } from "@/data/mockData";
import { UserSidebar } from "@/components/UserSidebar";
import { FilterControls } from "@/components/FilterControls";
import { WorkerDashboard } from "@/components/WorkerDashboard";
import { Activity } from "lucide-react";

const Index = () => {
  const [selectedWorker, setSelectedWorker] = useState<WorkerData | null>(mockWorkers[0]);
  const [activeFilter, setActiveFilter] = useState<'all' | 'high' | 'low'>('all');

  const filteredWorkers = useMemo(() => {
    if (activeFilter === 'all') return mockWorkers;
    return mockWorkers.filter(worker => 
      activeFilter === 'high' ? worker.riskLevel === 'high' : worker.riskLevel === 'low'
    );
  }, [activeFilter]);

  return (
    <div className="flex h-screen w-full overflow-hidden">
      {/* Sidebar */}
      <UserSidebar
        workers={filteredWorkers}
        selectedWorker={selectedWorker}
        onSelectWorker={setSelectedWorker}
      />

      {/* Main Content */}
      <div className="flex-1 flex flex-col overflow-hidden">
        {/* Header */}
        <header className="bg-gradient-to-r from-primary via-secondary to-primary p-6 shadow-lg">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              <Activity className="w-8 h-8 text-primary-foreground" />
              <h1 className="text-2xl font-bold text-primary-foreground">
                EARLY DETECTION OF LONG-TERM ILLNESS-RELATED ABSENCES
              </h1>
            </div>
          </div>
        </header>

        {/* Filter Controls */}
        <div className="bg-background border-b border-border p-4">
          <FilterControls
            activeFilter={activeFilter}
            onFilterChange={setActiveFilter}
          />
        </div>

        {/* Dashboard Content */}
        <main className="flex-1 overflow-auto bg-muted/30 p-6">
          {selectedWorker ? (
            <WorkerDashboard worker={selectedWorker} />
          ) : (
            <div className="flex items-center justify-center h-full">
              <div className="text-center">
                <Activity className="w-16 h-16 text-muted-foreground mx-auto mb-4" />
                <h2 className="text-2xl font-semibold text-foreground mb-2">
                  No Worker Selected
                </h2>
                <p className="text-muted-foreground">
                  Select a worker from the sidebar to view their dashboard
                </p>
              </div>
            </div>
          )}
        </main>
      </div>
    </div>
  );
};

export default Index;
