'use client';

import { useState } from 'react';
import { useRouter } from 'next/navigation';
import { useQuery } from '@tanstack/react-query';
import { ragApi } from '@/lib/api';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Input } from '@/components/ui/input';
import {
  Search,
  Bell,
  User,
  Sun,
  Moon,
  CheckCircle,
  XCircle,
  Loader2,
} from 'lucide-react';

export function Header() {
  const router = useRouter();
  const [searchQuery, setSearchQuery] = useState('');

  // Health check query
  const { data: health, isLoading } = useQuery({
    queryKey: ['health'],
    queryFn: () => ragApi.health(),
    refetchInterval: 30000,
  });

  const isHealthy = health?.status === 'ok' || health?.status === 'healthy';

  // Arama işlevi - Enter'a basınca chat sayfasına yönlendir
  const handleSearch = (e: React.FormEvent) => {
    e.preventDefault();
    const query = searchQuery.trim();
    if (query) {
      router.push(`/chat?q=${encodeURIComponent(query)}`);
      setSearchQuery('');
    }
  };

  return (
    <header className="flex h-16 items-center justify-between border-b bg-card px-6">
      {/* Search */}
      <div className="flex items-center gap-4">
        <form onSubmit={handleSearch} className="relative">
          <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
          <Input
            type="search"
            placeholder="Soru sor ve Enter'a bas..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="w-72 pl-10"
          />
        </form>
      </div>

      {/* Right side */}
      <div className="flex items-center gap-4">
        {/* API Status */}
        <div className="flex items-center gap-2">
          {isLoading ? (
            <Loader2 className="h-4 w-4 animate-spin text-muted-foreground" />
          ) : isHealthy ? (
            <Badge variant="success" className="gap-1">
              <CheckCircle className="h-3 w-3" />
              API Bağlı
            </Badge>
          ) : (
            <Badge variant="error" className="gap-1">
              <XCircle className="h-3 w-3" />
              API Bağlantısı Yok
            </Badge>
          )}
        </div>

        {/* Notifications */}
        <Button variant="ghost" size="icon">
          <Bell className="h-5 w-5" />
        </Button>

        {/* Theme Toggle */}
        <Button variant="ghost" size="icon">
          <Sun className="h-5 w-5 rotate-0 scale-100 transition-all dark:-rotate-90 dark:scale-0" />
          <Moon className="absolute h-5 w-5 rotate-90 scale-0 transition-all dark:rotate-0 dark:scale-100" />
        </Button>

        {/* User Menu */}
        <Button variant="ghost" size="icon">
          <User className="h-5 w-5" />
        </Button>
      </div>
    </header>
  );
}
