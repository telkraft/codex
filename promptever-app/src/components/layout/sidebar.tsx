'use client';

import Link from 'next/link';
import { usePathname } from 'next/navigation';
import { cn } from '@/lib/utils';
import { useUIStore } from '@/lib/store';
import { Button } from '@/components/ui/button';
import {
  LayoutDashboard,
  MessageSquare,
  BarChart3,
  Settings,
  Database,
  Brain,
  ChevronLeft,
  ChevronRight,
  Zap,
  LucideIcon,
} from 'lucide-react';

// Navigation item type definition
interface NavigationItem {
  name: string;
  href: string;
  icon: LucideIcon;
  badge?: string;
}

const navigation: NavigationItem[] = [
  {
    name: 'Gösterge Paneli',
    href: '/',
    icon: LayoutDashboard,
  },
  {
    name: 'Sohbet',
    href: '/chat',
    icon: MessageSquare,
  },
  {
    name: 'Analitik',
    href: '/analytics',
    icon: BarChart3,
  },
  {
    name: 'Referans Sorgular',
    href: '/quick-queries',
    icon: Zap,
  },
  {
    name: 'Kayıt Gezgini',
    href: '/lrs',
    icon: Database,
  },
  {
    name: 'Ontoloji',
    href: '/ontology',
    icon: Brain,
  },
  {
    name: 'Ayarlar',
    href: '/settings',
    icon: Settings,
  },
];

export function Sidebar() {
  const pathname = usePathname();
  const { sidebarOpen, toggleSidebar } = useUIStore();

  return (
    <aside
      className={cn(
        'relative flex flex-col border-r bg-card transition-all duration-300',
        sidebarOpen ? 'w-64' : 'w-16'
      )}
    >
      {/* Logo */}
      <div className="flex h-16 items-center justify-between border-b px-4">
        {sidebarOpen && (
          <Link href="/" className="flex items-center gap-2">
            <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-primary">
              <span className="text-lg font-bold text-primary-foreground">P</span>
            </div>
            <span className="text-xl font-bold text-foreground">Promptever</span>
          </Link>
        )}
        <Button
          variant="ghost"
          size="icon"
          onClick={toggleSidebar}
          className={cn(!sidebarOpen && 'mx-auto')}
        >
          {sidebarOpen ? (
            <ChevronLeft className="h-4 w-4" />
          ) : (
            <ChevronRight className="h-4 w-4" />
          )}
        </Button>
      </div>

      {/* Navigation */}
      <nav className="flex-1 space-y-1 p-2">
        {navigation.map((item) => {
          const isActive = pathname === item.href;
          return (
            <Link
              key={item.name}
              href={item.href}
              className={cn(
                'flex items-center gap-3 rounded-lg px-3 py-2 text-sm font-medium transition-colors',
                isActive
                  ? 'bg-primary text-primary-foreground'
                  : 'text-muted-foreground hover:bg-accent hover:text-accent-foreground',
                !sidebarOpen && 'justify-center'
              )}
              title={!sidebarOpen ? item.name : undefined}
            >
              <item.icon className="h-5 w-5 flex-shrink-0" />
              {sidebarOpen && (
                <span className="flex-1">{item.name}</span>
              )}
              {sidebarOpen && item.badge && (
                <span className={cn(
                  "text-[10px] px-1.5 py-0.5 rounded-full",
                  isActive 
                    ? "bg-primary-foreground/20 text-primary-foreground"
                    : "bg-primary/10 text-primary"
                )}>
                  {item.badge}
                </span>
              )}
            </Link>
          );
        })}
      </nav>

      {/* Footer */}
      {sidebarOpen && (
        <div className="border-t p-4">
          <p className="text-xs text-muted-foreground">
            Promptever v1.0.0
          </p>
          <p className="text-xs text-muted-foreground">
            Enterprise Experience Analytics
          </p>
        </div>
      )}
    </aside>
  );
}
