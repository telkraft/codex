'use client';

import { useQuery } from '@tanstack/react-query';
import { ragApi } from '@/lib/api';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import {
  CheckCircle,
  XCircle,
  Loader2,
  Server,
  Database,
  Brain,
  Globe,
} from 'lucide-react';

interface ServiceStatus {
  name: string;
  status: 'healthy' | 'unhealthy' | 'loading';
  icon: React.ElementType;
  description: string;
}

export function SystemStatus() {
  const { data: health, isLoading } = useQuery({
    queryKey: ['health'],
    queryFn: () => ragApi.health(),
    refetchInterval: 30000,
  });

  const services: ServiceStatus[] = [
    {
      name: 'RAG API',
      status: isLoading
        ? 'loading'
        : health?.status === 'ok' || health?.status === 'healthy'
        ? 'healthy'
        : 'unhealthy',
      icon: Server,
      description: 'FastAPI Backend',
    },
    {
      name: 'Qdrant',
      status: isLoading
        ? 'loading'
        : health?.details?.qdrant === 'alive'
        ? 'healthy'
        : 'unhealthy',
      icon: Database,
      description: 'Vector Database',
    },
    {
      name: 'LLM',
      status: isLoading
        ? 'loading'
        : health?.details?.ollama === 'alive'
        ? 'healthy'
        : 'unhealthy',
      icon: Brain,
      description: 'Language Model',
    },
    {
      name: 'MongoDB LRS',
      status: isLoading
        ? 'loading'
        : health?.details?.mongodb === 'alive'
        ? 'healthy'
        : 'unhealthy',
      icon: Globe,
      description: 'Experience Store',
    },
  ];

  const getStatusIcon = (status: ServiceStatus['status']) => {
    switch (status) {
      case 'healthy':
        return <CheckCircle className="h-4 w-4 text-green-500" />;
      case 'unhealthy':
        return <XCircle className="h-4 w-4 text-red-500" />;
      case 'loading':
        return <Loader2 className="h-4 w-4 animate-spin text-muted-foreground" />;
    }
  };

  const getStatusBadge = (status: ServiceStatus['status']) => {
    switch (status) {
      case 'healthy':
        return <Badge variant="success">Çalışıyor</Badge>;
      case 'unhealthy':
        return <Badge variant="error">Bağlantı Yok</Badge>;
      case 'loading':
        return <Badge variant="secondary">Kontrol Ediliyor</Badge>;
    }
  };

  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-lg">Sistem Durumu</CardTitle>
      </CardHeader>
      <CardContent className="space-y-3">
        {services.map((service) => (
          <div
            key={service.name}
            className="flex items-center justify-between rounded-lg border p-3"
          >
            <div className="flex items-center gap-3">
              <div className="rounded-lg bg-muted p-2">
                <service.icon className="h-4 w-4 text-muted-foreground" />
              </div>
              <div>
                <p className="text-sm font-medium">{service.name}</p>
                <p className="text-xs text-muted-foreground">
                  {service.description}
                </p>
              </div>
            </div>
            <div className="flex items-center gap-2">
              {getStatusIcon(service.status)}
              {getStatusBadge(service.status)}
            </div>
          </div>
        ))}
      </CardContent>
    </Card>
  );
}
