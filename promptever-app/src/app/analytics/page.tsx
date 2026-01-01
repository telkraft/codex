'use client';

import { useState, useEffect } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { useSettingsStore } from '@/lib/store';
import { ragApi } from '@/lib/api';
import {
  BarChart3,
  RefreshCw,
  Calendar,
  Sun,
  Truck,
} from 'lucide-react';
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  LineChart,
  Line,
  Legend,
} from 'recharts';

interface ChartData {
  year?: number;
  season?: string;
  vehicleType?: string;
  verbType?: string;
  count?: number;
  BAKIM?: number;
  ONARIM?: number;
}

const COLORS = {
  BAKIM: '#0088FE',
  ONARIM: '#FF8042',
  count: '#8884d8',
};

export default function AnalyticsPage() {
  const { collection } = useSettingsStore();
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [yearData, setYearData] = useState<ChartData[]>([]);
  const [seasonData, setSeasonData] = useState<ChartData[]>([]);
  const [vehicleData, setVehicleData] = useState<ChartData[]>([]);

  const runQuery = async (query: string): Promise<any[]> => {
    try {
      const response = await ragApi.chat({
        query,
        collection,
        use_llm: false,
        limit: 5000,
        model: undefined,
        role: 'servis_analisti',
        behavior: 'balanced',
      });

      const tables = response.tables || [];
      if (tables.length > 0 && tables[0].rows) {
        return tables[0].rows;
      }
      // Fallback to data.rows
      const data = response.data as any;
      if (data?.rows) {
        return data.rows;
      }
      return [];
    } catch (err) {
      console.error('Query error:', err);
      return [];
    }
  };

  // verbType varsa pivot yap (BAKIM/ONARIM ayrımı)
  const pivotData = (rows: any[], indexCol: string): ChartData[] => {
    const hasVerbType = rows.some(r => r.verbType);
    
    if (!hasVerbType) {
      // verbType yoksa direkt kullan
      return rows
        .filter(r => r[indexCol] != null)
        .map(r => ({
          [indexCol]: r[indexCol],
          count: r.count || 0,
        }))
        .sort((a, b) => (b.count || 0) - (a.count || 0));
    }

    // verbType varsa pivot yap
    const grouped: Record<string, ChartData> = {};

    rows.forEach((row) => {
      const key = row[indexCol];
      if (key == null) return;
      
      if (!grouped[key]) {
        grouped[key] = { [indexCol]: key, BAKIM: 0, ONARIM: 0 };
      }
      const verb = (row.verbType || '').toUpperCase();
      const count = row.count || 0;
      if (verb.includes('BAKIM')) {
        grouped[key].BAKIM = (grouped[key].BAKIM || 0) + count;
      } else if (verb.includes('ONARIM')) {
        grouped[key].ONARIM = (grouped[key].ONARIM || 0) + count;
      }
    });

    return Object.values(grouped).sort((a, b) => {
      const aVal = a[indexCol as keyof ChartData];
      const bVal = b[indexCol as keyof ChartData];
      if (typeof aVal === 'number' && typeof bVal === 'number') {
        return aVal - bVal;
      }
      return String(aVal).localeCompare(String(bVal));
    });
  };

  const fetchAllData = async () => {
    setLoading(true);
    setError(null);

    try {
      // 1. Yıllara göre
      const yearRows = await runQuery('Yıllara göre bakım ve onarım işlemlerinin dağılımı nedir?');
      if (yearRows.length > 0) {
        setYearData(pivotData(yearRows, 'year'));
      }

      // 2. Mevsimlere göre
      const seasonRows = await runQuery('Mevsimlere göre bakım ve onarım işlemlerinin dağılımı nedir?');
      if (seasonRows.length > 0) {
        setSeasonData(pivotData(seasonRows, 'season'));
      }

      // 3. Araç tiplerine göre
      const vehicleRows = await runQuery('Araç tiplerine göre bakım ve onarım işlemlerinin dağılımı nedir?');
      if (vehicleRows.length > 0) {
        setVehicleData(pivotData(vehicleRows, 'vehicleType'));
      }
    } catch (err) {
      setError('API bağlantı hatası: ' + String(err));
    }

    setLoading(false);
  };

  useEffect(() => {
    fetchAllData();
  }, [collection]);

  // Chart'ta BAKIM/ONARIM var mı kontrol et
  const hasPivot = (data: ChartData[]) => data.some(d => d.BAKIM !== undefined || d.ONARIM !== undefined);

  return (
    <div className="container mx-auto p-6 space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <BarChart3 className="h-8 w-8 text-primary" />
          <div>
            <h1 className="text-2xl font-bold">Genel Bakış</h1>
            <p className="text-muted-foreground">LRS İstatistikleri</p>
          </div>
        </div>
        <Button onClick={fetchAllData} variant="outline" disabled={loading}>
          <RefreshCw className={`h-4 w-4 mr-2 ${loading ? 'animate-spin' : ''}`} />
          Yenile
        </Button>
      </div>

      {error && (
        <div className="bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 rounded-lg p-3">
          <p className="text-sm text-red-800 dark:text-red-200">{error}</p>
        </div>
      )}

      {/* Chart 1: Yıllara Göre */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Calendar className="h-5 w-5" />
            Yıllara Göre Bakım & Onarım Dağılımı
          </CardTitle>
        </CardHeader>
        <CardContent>
          {yearData.length > 0 ? (
            <ResponsiveContainer width="100%" height={300}>
              <LineChart data={yearData}>
                <CartesianGrid strokeDasharray="3 3" />
                <XAxis dataKey="year" />
                <YAxis />
                <Tooltip />
                <Legend />
                {hasPivot(yearData) ? (
                  <>
                    <Line type="monotone" dataKey="BAKIM" stroke={COLORS.BAKIM} strokeWidth={2} name="Bakım" />
                    <Line type="monotone" dataKey="ONARIM" stroke={COLORS.ONARIM} strokeWidth={2} name="Onarım" />
                  </>
                ) : (
                  <Line type="monotone" dataKey="count" stroke={COLORS.count} strokeWidth={2} name="İşlem" />
                )}
              </LineChart>
            </ResponsiveContainer>
          ) : (
            <p className="text-center text-muted-foreground py-10">
              {loading ? 'Yükleniyor...' : 'Veri bulunamadı'}
            </p>
          )}
        </CardContent>
      </Card>

      {/* Chart 2: Mevsimlere Göre */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Sun className="h-5 w-5" />
            Mevsimlere Göre Bakım & Onarım Dağılımı
          </CardTitle>
        </CardHeader>
        <CardContent>
          {seasonData.length > 0 ? (
            <ResponsiveContainer width="100%" height={300}>
              <BarChart data={seasonData}>
                <CartesianGrid strokeDasharray="3 3" />
                <XAxis dataKey="season" />
                <YAxis />
                <Tooltip />
                <Legend />
                {hasPivot(seasonData) ? (
                  <>
                    <Bar dataKey="BAKIM" fill={COLORS.BAKIM} name="Bakım" />
                    <Bar dataKey="ONARIM" fill={COLORS.ONARIM} name="Onarım" />
                  </>
                ) : (
                  <Bar dataKey="count" fill={COLORS.count} name="İşlem" />
                )}
              </BarChart>
            </ResponsiveContainer>
          ) : (
            <p className="text-center text-muted-foreground py-10">
              {loading ? 'Yükleniyor...' : 'Veri bulunamadı'}
            </p>
          )}
        </CardContent>
      </Card>

      {/* Chart 3: Araç Tiplerine Göre */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Truck className="h-5 w-5" />
            Araç Tiplerine Göre Bakım & Onarım Dağılımı
          </CardTitle>
        </CardHeader>
        <CardContent>
          {vehicleData.length > 0 ? (
            <ResponsiveContainer width="100%" height={300}>
              <BarChart data={vehicleData} layout="vertical">
                <CartesianGrid strokeDasharray="3 3" />
                <XAxis type="number" />
                <YAxis dataKey="vehicleType" type="category" width={80} tick={{ fontSize: 12 }} />
                <Tooltip />
                <Legend />
                {hasPivot(vehicleData) ? (
                  <>
                    <Bar dataKey="BAKIM" fill={COLORS.BAKIM} name="Bakım" />
                    <Bar dataKey="ONARIM" fill={COLORS.ONARIM} name="Onarım" />
                  </>
                ) : (
                  <Bar dataKey="count" fill={COLORS.count} name="İşlem Sayısı" />
                )}
              </BarChart>
            </ResponsiveContainer>
          ) : (
            <p className="text-center text-muted-foreground py-10">
              {loading ? 'Yükleniyor...' : 'Veri bulunamadı'}
            </p>
          )}
        </CardContent>
      </Card>
    </div>
  );
}