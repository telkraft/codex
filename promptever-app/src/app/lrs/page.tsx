'use client';

import { useState, useEffect } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import {
  Database,
  ChevronLeft,
  ChevronRight,
  RefreshCw,
  X,
  Truck,
  Wrench,
  Calendar,
  Package,
} from 'lucide-react';

interface Statement {
  id: string;
  stored: string;
  actor: {
    name?: string;
    account?: { name: string };
  };
  verb: {
    id: string;
    display?: { 'tr-TR'?: string; 'en-US'?: string };
  };
  object: {
    id: string;
    definition?: {
      name?: { 'tr-TR'?: string; 'en-US'?: string };
    };
  };
  context?: any;
  result?: any;
}

const PAGE_SIZE = 20;

export default function LRSExplorerPage() {
  const [statements, setStatements] = useState<Statement[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [page, setPage] = useState(1);
  const [total, setTotal] = useState(0);
  const [selectedStatement, setSelectedStatement] = useState<Statement | null>(null);

  const fetchStatements = async (pageNum: number) => {
    setLoading(true);
    setError(null);
    try {
      const skip = (pageNum - 1) * PAGE_SIZE;
      const response = await fetch(
        `https://app.promptever.com/api/rag/lrs/statements?limit=${PAGE_SIZE}&skip=${skip}`
      );
      
      if (!response.ok) throw new Error('Statements yüklenemedi');
      
      const data = await response.json();
      setStatements(data.statements || []);
      setTotal(data.total || 0);
    } catch (err) {
      setError(String(err));
    }
    setLoading(false);
  };

  useEffect(() => {
    fetchStatements(page);
  }, [page]);

  const totalPages = Math.ceil(total / PAGE_SIZE);

  const getVerbDisplay = (verb: Statement['verb']) => {
    const display = verb.display?.['tr-TR'] || verb.display?.['en-US'] || '';
    if (verb.id.includes('maintained')) return { text: 'Bakım', color: 'bg-blue-100 text-blue-800' };
    if (verb.id.includes('repaired')) return { text: 'Onarım', color: 'bg-orange-100 text-orange-800' };
    if (verb.id.includes('inspected')) return { text: 'Kontrol', color: 'bg-green-100 text-green-800' };
    return { text: display || 'Bilinmiyor', color: 'bg-gray-100 text-gray-800' };
  };

  const getActorName = (actor: Statement['actor']) => {
    if (actor.name) return actor.name;
    if (actor.account?.name) {
      const name = actor.account.name;
      if (name.startsWith('vehicle/')) return `Araç ${name.split('/')[1]}`;
      return name;
    }
    return 'Bilinmiyor';
  };

  const getObjectName = (obj: Statement['object']) => {
    return obj.definition?.name?.['tr-TR'] || obj.definition?.name?.['en-US'] || obj.id.split('/').pop() || 'Bilinmiyor';
  };

  const formatDate = (dateStr: string) => {
    try {
      return new Date(dateStr).toLocaleString('tr-TR');
    } catch {
      return dateStr;
    }
  };

  return (
    <div className="container mx-auto p-6 space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <Database className="h-8 w-8 text-primary" />
          <div>
            <h1 className="text-2xl font-bold">Kayıt Gezgini</h1>
            <p className="text-muted-foreground">
              {total.toLocaleString('tr-TR')} xAPI Statement
            </p>
          </div>
        </div>
        <Button onClick={() => fetchStatements(page)} variant="outline" disabled={loading}>
          <RefreshCw className={`h-4 w-4 mr-2 ${loading ? 'animate-spin' : ''}`} />
          Yenile
        </Button>
      </div>

      {error && (
        <div className="bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 rounded-lg p-3">
          <p className="text-sm text-red-800 dark:text-red-200">{error}</p>
        </div>
      )}

      {/* Statements List */}
      <Card>
        <CardHeader className="pb-3">
          <div className="flex items-center justify-between">
            <CardTitle>xAPI Statements</CardTitle>
            <div className="flex items-center gap-2 text-sm text-muted-foreground">
              Sayfa {page} / {totalPages || 1}
            </div>
          </div>
        </CardHeader>
        <CardContent>
          {loading ? (
            <div className="flex items-center justify-center py-10">
              <RefreshCw className="h-8 w-8 animate-spin text-muted-foreground" />
            </div>
          ) : statements.length === 0 ? (
            <p className="text-center text-muted-foreground py-10">Statement bulunamadı</p>
          ) : (
            <div className="space-y-2">
              {statements.map((stmt) => {
                const verb = getVerbDisplay(stmt.verb);
                return (
                  <div
                    key={stmt.id}
                    onClick={() => setSelectedStatement(stmt)}
                    className="flex items-center justify-between p-3 rounded-lg border hover:bg-muted/50 cursor-pointer transition-colors"
                  >
                    <div className="flex items-center gap-3 flex-1 min-w-0">
                      <div className="flex-shrink-0">
                        <Truck className="h-5 w-5 text-muted-foreground" />
                      </div>
                      <div className="flex-1 min-w-0">
                        <div className="flex items-center gap-2 flex-wrap">
                          <span className="font-medium">{getActorName(stmt.actor)}</span>
                          <Badge className={verb.color}>{verb.text}</Badge>
                          <span className="text-muted-foreground truncate">
                            '{getObjectName(stmt.object)}'
                          </span>
                        </div>
                      </div>
                    </div>
                    <div className="text-xs text-muted-foreground flex-shrink-0 ml-2">
                      {formatDate(stmt.stored)}
                    </div>
                  </div>
                );
              })}
            </div>
          )}

          {/* Pagination */}
          <div className="flex items-center justify-between mt-4 pt-4 border-t">
            <Button
              variant="outline"
              size="sm"
              onClick={() => setPage(p => Math.max(1, p - 1))}
              disabled={page <= 1 || loading}
            >
              <ChevronLeft className="h-4 w-4 mr-1" />
              Önceki
            </Button>
            <div className="flex items-center gap-1">
              {[...Array(Math.min(5, totalPages))].map((_, i) => {
                let pageNum: number;
                if (totalPages <= 5) {
                  pageNum = i + 1;
                } else if (page <= 3) {
                  pageNum = i + 1;
                } else if (page >= totalPages - 2) {
                  pageNum = totalPages - 4 + i;
                } else {
                  pageNum = page - 2 + i;
                }
                return (
                  <Button
                    key={pageNum}
                    variant={page === pageNum ? 'default' : 'outline'}
                    size="sm"
                    onClick={() => setPage(pageNum)}
                    disabled={loading}
                    className="w-8 h-8 p-0"
                  >
                    {pageNum}
                  </Button>
                );
              })}
            </div>
            <Button
              variant="outline"
              size="sm"
              onClick={() => setPage(p => Math.min(totalPages, p + 1))}
              disabled={page >= totalPages || loading}
            >
              Sonraki
              <ChevronRight className="h-4 w-4 ml-1" />
            </Button>
          </div>
        </CardContent>
      </Card>

      {/* Statement Detail Modal */}
      {selectedStatement && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
          <Card className="w-full max-w-3xl max-h-[80vh] overflow-hidden">
            <CardHeader className="flex flex-row items-center justify-between">
              <CardTitle className="text-lg">Statement Detayı</CardTitle>
              <Button
                variant="ghost"
                size="icon"
                onClick={() => setSelectedStatement(null)}
              >
                <X className="h-4 w-4" />
              </Button>
            </CardHeader>
            <CardContent className="overflow-auto max-h-[60vh]">
              <pre className="text-xs bg-muted p-4 rounded-lg overflow-auto">
                {JSON.stringify(selectedStatement, null, 2)}
              </pre>
            </CardContent>
          </Card>
        </div>
      )}
    </div>
  );
}