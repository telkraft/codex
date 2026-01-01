'use client';

import { useChatStore, Message } from '@/lib/store';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import Link from 'next/link';
import {
  Search,
  MessageSquare,
  Clock,
  TrendingUp,
  Database,
  BarChart3,
} from 'lucide-react';

export function RecentActivity() {
  const { messages } = useChatStore();

  // Sadece kullanıcı sorgularını filtrele (son 5 tanesi)
  const userQueries = messages
    .filter((msg) => msg.role === 'user')
    .slice(-5)
    .reverse(); // En son sorgu en üstte

  // Eğer hiç sorgu yoksa bölümü gösterme
  if (userQueries.length === 0) {
    return null;
  }

  // Intent'e göre icon ve renk belirle
  const getQueryInfo = (msg: Message) => {
    const content = msg.content.toLowerCase();
    
    // Trend/değişim sorguları
    if (content.includes('trend') || content.includes('değişim') || content.includes('artış') || content.includes('azalış')) {
      return { icon: TrendingUp, color: 'text-green-500', badge: 'Trend', badgeColor: 'success' };
    }
    // Dağılım/istatistik sorguları
    if (content.includes('dağılım') || content.includes('oran') || content.includes('sayı')) {
      return { icon: BarChart3, color: 'text-blue-500', badge: 'İstatistik', badgeColor: 'statistical' };
    }
    // Veri sorguları
    if (content.includes('hangi') || content.includes('liste') || content.includes('en çok') || content.includes('en az')) {
      return { icon: Database, color: 'text-purple-500', badge: 'Veri', badgeColor: 'hybrid' };
    }
    // Varsayılan
    return { icon: Search, color: 'text-muted-foreground', badge: 'Sorgu', badgeColor: 'secondary' };
  };

  // Zaman formatla
  const formatTime = (date: Date | string) => {
    try {
      const d = typeof date === 'string' ? new Date(date) : date;
      const now = new Date();
      const diffMs = now.getTime() - d.getTime();
      const diffMin = Math.floor(diffMs / 60000);
      const diffHour = Math.floor(diffMs / 3600000);
      const diffDay = Math.floor(diffMs / 86400000);

      if (diffMin < 1) return 'Az önce';
      if (diffMin < 60) return `${diffMin} dk önce`;
      if (diffHour < 24) return `${diffHour} saat önce`;
      return `${diffDay} gün önce`;
    } catch {
      return '';
    }
  };

  // Sorguyu kısalt
  const truncateQuery = (text: string, maxLength: number = 50) => {
    if (text.length <= maxLength) return text;
    return text.slice(0, maxLength) + '...';
  };

  return (
    <Card>
      <CardHeader className="flex flex-row items-center justify-between pb-2">
        <CardTitle className="text-lg flex items-center gap-2">
          <MessageSquare className="h-4 w-4" />
          Son Sorgular
        </CardTitle>
        <Link 
          href="/chat" 
          className="text-xs text-muted-foreground hover:text-primary transition-colors"
        >
          Tümünü gör →
        </Link>
      </CardHeader>
      <CardContent className="space-y-3">
        {userQueries.map((msg) => {
          const queryInfo = getQueryInfo(msg);
          const IconComponent = queryInfo.icon;
          
          return (
            <Link 
              key={msg.id} 
              href="/chat"
              className="block"
            >
              <div className="flex items-start gap-3 rounded-lg p-2 hover:bg-accent transition-colors cursor-pointer">
                <div className="rounded-lg bg-muted p-2 shrink-0">
                  <IconComponent className={`h-4 w-4 ${queryInfo.color}`} />
                </div>
                <div className="flex-1 space-y-1 min-w-0">
                  <div className="flex items-center gap-2 flex-wrap">
                    <p className="text-sm font-medium truncate flex-1">
                      {truncateQuery(msg.content)}
                    </p>
                    <Badge 
                      variant={queryInfo.badgeColor as any} 
                      className="text-[10px] px-1.5 py-0 shrink-0"
                    >
                      {queryInfo.badge}
                    </Badge>
                  </div>
                  <div className="flex items-center gap-1 text-xs text-muted-foreground">
                    <Clock className="h-3 w-3" />
                    <span>{formatTime(msg.timestamp)}</span>
                  </div>
                </div>
              </div>
            </Link>
          );
        })}
      </CardContent>
    </Card>
  );
}
