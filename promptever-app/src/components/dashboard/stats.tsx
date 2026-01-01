'use client';

import { useQuery } from '@tanstack/react-query';
import { ragApi } from '@/lib/api';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { formatNumber } from '@/lib/utils';
import {
  Database,
  Truck,
  Wrench,
  AlertTriangle,
  Loader2,
} from 'lucide-react';

interface StatsData {
  totalStatements: number;
  uniqueVehicles: number;
  faultCodeRatio: number;
  maintenanceRatio?: number;
  repairRatio?: number;
}

export function DashboardStats() {
  // Ana istatistikler
  const { data: lrsData, isLoading: lrsLoading, error: lrsError } = useQuery({
    queryKey: ['lrs-stats'],
    queryFn: () => ragApi.getLRSStats(),
    refetchInterval: 60000,
  });

  // Bakım/Onarım oranları için ek sorgu
  const { data: ratioData, isLoading: ratioLoading } = useQuery({
    queryKey: ['operation-ratio'],
    queryFn: async () => {
      try {
        const response = await ragApi.chat({
          query: 'İşlem tipi dağılımı nedir?',
          collection: 'man_local_service_maintenance',
          use_llm: false,
          limit: 100,
        });
        
        const tables = response.tables || [];
        const rows = tables[0]?.rows || (response.data as any)?.rows || [];
        
        let bakimCount = 0;
        let onarimCount = 0;
        let totalCount = 0;
        
        rows.forEach((row: any) => {
          const verb = (row.verbType || '').toUpperCase();
          const count = row.count || 0;
          totalCount += count;
          
          if (verb.includes('BAKIM')) {
            bakimCount += count;
          } else if (verb.includes('ONARIM')) {
            onarimCount += count;
          }
        });
        
        return {
          maintenanceRatio: totalCount > 0 ? (bakimCount / totalCount) * 100 : 0,
          repairRatio: totalCount > 0 ? (onarimCount / totalCount) * 100 : 0,
        };
      } catch {
        return { maintenanceRatio: 0, repairRatio: 0 };
      }
    },
    refetchInterval: 60000,
  });

  const stats = lrsData?.data;
  const isLoading = lrsLoading || ratioLoading;

  const statCards = [
    {
      title: 'Toplam Statement',
      value: stats?.totalStatements ?? 0,
      icon: Database,
      description: 'LRS kayıt sayısı',
      color: 'text-blue-500',
      show: true,
    },
    {
      title: 'Araç Sayısı',
      value: stats?.uniqueVehicles ?? 0,
      icon: Truck,
      description: 'Benzersiz araç',
      color: 'text-green-500',
      show: true,
    },
    {
      title: 'Bakım Oranı',
      value: ratioData?.maintenanceRatio ?? 0,
      icon: Wrench,
      description: 'Toplam işlemlerde',
      color: 'text-cyan-500',
      isPercentage: true,
      show: (ratioData?.maintenanceRatio ?? 0) > 0,
    },
    {
      title: 'Onarım Oranı',
      value: ratioData?.repairRatio ?? 0,
      icon: AlertTriangle,
      description: 'Toplam işlemlerde',
      color: 'text-orange-500',
      isPercentage: true,
      show: (ratioData?.repairRatio ?? 0) > 0,
    },
  ];

  // Sadece gösterilecek kartları filtrele
  const visibleCards = statCards.filter(card => card.show);

  if (lrsError) {
    return (
      <Card>
        <CardContent className="flex items-center justify-center py-8">
          <p className="text-muted-foreground">
            İstatistikler yüklenemedi. API bağlantısını kontrol edin.
          </p>
        </CardContent>
      </Card>
    );
  }

  return (
    <div className={`grid gap-4 md:grid-cols-2 lg:grid-cols-${visibleCards.length}`}>
      {visibleCards.map((stat) => (
        <Card key={stat.title}>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">
              {stat.title}
            </CardTitle>
            <stat.icon className={`h-4 w-4 ${stat.color}`} />
          </CardHeader>
          <CardContent>
            {isLoading ? (
              <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
            ) : (
              <>
                <div className="text-2xl font-bold">
                  {stat.isPercentage 
                    ? `${Number(stat.value).toFixed(1)}%`
                    : formatNumber(Number(stat.value))
                  }
                </div>
                <p className="text-xs text-muted-foreground">
                  {stat.description}
                </p>
              </>
            )}
          </CardContent>
        </Card>
      ))}
    </div>
  );
}