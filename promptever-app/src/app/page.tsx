import { DashboardStats } from '@/components/dashboard/stats';
import { RecentActivity } from '@/components/dashboard/recent-activity';
import { QuickActions } from '@/components/dashboard/quick-actions';
import { SystemStatus } from '@/components/dashboard/system-status';

export default function DashboardPage() {
  return (
    <div className="container py-6 space-y-6">
      {/* Page Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold tracking-tight">Dashboard</h1>
          <p className="text-muted-foreground">
            Kurumsal deneyim analitiği ve içgörüler
          </p>
        </div>
      </div>

      {/* Stats Overview */}
      <DashboardStats />

      {/* Main Content Grid */}
      <div className="grid gap-6 md:grid-cols-2 lg:grid-cols-3">
        {/* Quick Actions */}
        <div className="lg:col-span-1">
          <QuickActions />
        </div>

        {/* Recent Activity */}
        <div className="lg:col-span-1">
          <RecentActivity />
        </div>

        {/* System Status */}
        <div className="lg:col-span-1">
          <SystemStatus />
        </div>
      </div>
    </div>
  );
}
