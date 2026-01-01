'use client';

import Link from 'next/link';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import {
  MessageSquare,
  BarChart3,
  Brain,
  Zap,
} from 'lucide-react';

const quickActions = [
  {
    title: 'Yeni Sohbet',
    description: 'AI ile analiz başlat',
    icon: MessageSquare,
    href: '/chat',
    color: 'bg-blue-500',
  },
  {
    title: 'Genel Özet',
    description: 'Analitik grafikler',
    icon: BarChart3,
    href: '/analytics',
    color: 'bg-green-500',
  },
  {
    title: 'Ontoloji',
    description: 'Veri şeması ve boyutlar',
    icon: Brain,
    href: '/ontology',
    color: 'bg-purple-500',
  },
  {
    title: 'Referans Sorgular',
    description: 'Önceden tanımlı sorgular',
    icon: Zap,
    href: '/quick-queries',
    color: 'bg-orange-500',
  },
];

export function QuickActions() {
  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-lg">Hızlı Eylemler</CardTitle>
      </CardHeader>
      <CardContent className="space-y-2">
        {quickActions.map((action) => (
          <Link key={action.title} href={action.href}>
            <Button
              variant="ghost"
              className="w-full justify-start gap-3 h-auto py-3"
            >
              <div className={`rounded-lg p-2 ${action.color}`}>
                <action.icon className="h-4 w-4 text-white" />
              </div>
              <div className="text-left">
                <p className="font-medium">{action.title}</p>
                <p className="text-xs text-muted-foreground">
                  {action.description}
                </p>
              </div>
            </Button>
          </Link>
        ))}
      </CardContent>
    </Card>
  );
}