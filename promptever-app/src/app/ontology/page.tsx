'use client';

import { useState, useEffect } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { ragApi } from '@/lib/api';
import {
  Database,
  Layers,
  Calculator,
  MessageSquare,
  RefreshCw,
  ChevronDown,
  ChevronRight,
  Truck,
  Wrench,
  Package,
  MapPin,
  Calendar,
  Users,
  FileText,
} from 'lucide-react';

interface Dimension {
  key: string;
  name: string;
  category: string;
  type: string;
  examples: (string | number)[];
}

interface Metric {
  key: string;
  name: string;
  unit: string;
  type: string;
}

interface Verb {
  id: string;
  display: string;
  description: string;
}

interface SchemaData {
  version: string;
  description: string;
  dimensions: Dimension[];
  metrics: Metric[];
  verbs: Verb[];
  example_queries: string[];
}

const CATEGORY_ICONS: Record<string, React.ElementType> = {
  'Araç': Truck,
  'İşlem': Wrench,
  'Malzeme': Package,
  'Lokasyon': MapPin,
  'Müşteri': Users,
  'İş Emri': FileText,
  'Zaman': Calendar,
};

const CATEGORY_COLORS: Record<string, string> = {
  'Araç': 'bg-blue-100 text-blue-800 dark:bg-blue-900/30 dark:text-blue-300',
  'İşlem': 'bg-orange-100 text-orange-800 dark:bg-orange-900/30 dark:text-orange-300',
  'Malzeme': 'bg-green-100 text-green-800 dark:bg-green-900/30 dark:text-green-300',
  'Lokasyon': 'bg-purple-100 text-purple-800 dark:bg-purple-900/30 dark:text-purple-300',
  'Müşteri': 'bg-pink-100 text-pink-800 dark:bg-pink-900/30 dark:text-pink-300',
  'İş Emri': 'bg-yellow-100 text-yellow-800 dark:bg-yellow-900/30 dark:text-yellow-300',
  'Zaman': 'bg-cyan-100 text-cyan-800 dark:bg-cyan-900/30 dark:text-cyan-300',
};

const TYPE_BADGES: Record<string, string> = {
  'string': 'bg-gray-100 text-gray-700',
  'enum': 'bg-indigo-100 text-indigo-700',
  'integer': 'bg-emerald-100 text-emerald-700',
  'date': 'bg-rose-100 text-rose-700',
  'count': 'bg-blue-100 text-blue-700',
  'sum': 'bg-green-100 text-green-700',
  'avg': 'bg-amber-100 text-amber-700',
  'min': 'bg-cyan-100 text-cyan-700',
  'max': 'bg-red-100 text-red-700',
};

export default function OntologyPage() {
  const [schema, setSchema] = useState<SchemaData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [expandedCategories, setExpandedCategories] = useState<Set<string>>(new Set());

  const fetchSchema = async () => {
    setLoading(true);
    setError(null);
    try {
      const response = await fetch('https://app.promptever.com/api/rag/schema');
      if (!response.ok) throw new Error('Schema yüklenemedi');
      const data = await response.json();
      setSchema(data);
    // Tüm kategorileri aç
      const categories = new Set<string>(data.dimensions.map((d: Dimension) => d.category));
      setExpandedCategories(categories);
    } catch (err) {
      setError(String(err));
    }
    setLoading(false);
  };

  useEffect(() => {
    fetchSchema();
  }, []);

  const toggleCategory = (category: string) => {
    setExpandedCategories(prev => {
      const newSet = new Set(prev);
      if (newSet.has(category)) {
        newSet.delete(category);
      } else {
        newSet.add(category);
      }
      return newSet;
    });
  };

  // Dimension'ları kategorilere göre grupla
  const groupedDimensions = schema?.dimensions.reduce((acc, dim) => {
    if (!acc[dim.category]) acc[dim.category] = [];
    acc[dim.category].push(dim);
    return acc;
  }, {} as Record<string, Dimension[]>) || {};

  if (loading) {
    return (
      <div className="container mx-auto p-6 flex items-center justify-center min-h-[400px]">
        <RefreshCw className="h-8 w-8 animate-spin text-muted-foreground" />
      </div>
    );
  }

  if (error) {
    return (
      <div className="container mx-auto p-6">
        <Card className="border-red-200 bg-red-50 dark:bg-red-900/20">
          <CardContent className="pt-6">
            <p className="text-red-800 dark:text-red-200">{error}</p>
            <Button onClick={fetchSchema} variant="outline" className="mt-4">
              Tekrar Dene
            </Button>
          </CardContent>
        </Card>
      </div>
    );
  }

  return (
    <div className="container mx-auto p-6 space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <Database className="h-8 w-8 text-primary" />
          <div>
            <h1 className="text-2xl font-bold">Veri Ontolojisi</h1>
            <p className="text-muted-foreground">
              {schema?.description} • v{schema?.version}
            </p>
          </div>
        </div>
        <Button onClick={fetchSchema} variant="outline" size="sm">
          <RefreshCw className="h-4 w-4 mr-2" />
          Yenile
        </Button>
      </div>

      {/* Summary Cards */}
      <div className="grid gap-4 md:grid-cols-4">
        <Card>
          <CardContent className="pt-4">
            <div className="flex items-center gap-2">
              <Layers className="h-5 w-5 text-blue-500" />
              <span className="text-2xl font-bold">{schema?.dimensions.length}</span>
            </div>
            <p className="text-sm text-muted-foreground">Dimension</p>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="pt-4">
            <div className="flex items-center gap-2">
              <Calculator className="h-5 w-5 text-green-500" />
              <span className="text-2xl font-bold">{schema?.metrics.length}</span>
            </div>
            <p className="text-sm text-muted-foreground">Metric</p>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="pt-4">
            <div className="flex items-center gap-2">
              <Wrench className="h-5 w-5 text-orange-500" />
              <span className="text-2xl font-bold">{schema?.verbs.length}</span>
            </div>
            <p className="text-sm text-muted-foreground">Verb (İşlem)</p>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="pt-4">
            <div className="flex items-center gap-2">
              <MessageSquare className="h-5 w-5 text-purple-500" />
              <span className="text-2xl font-bold">{Object.keys(groupedDimensions).length}</span>
            </div>
            <p className="text-sm text-muted-foreground">Kategori</p>
          </CardContent>
        </Card>
      </div>

      <div className="grid gap-6 lg:grid-cols-2">
        {/* Dimensions */}
        <Card className="lg:col-span-1">
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Layers className="h-5 w-5" />
              Dimensions (Boyutlar)
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-3">
            {Object.entries(groupedDimensions).map(([category, dims]) => {
              const Icon = CATEGORY_ICONS[category] || Database;
              const isExpanded = expandedCategories.has(category);
              
              return (
                <div key={category} className="border rounded-lg overflow-hidden">
                  <button
                    onClick={() => toggleCategory(category)}
                    className="w-full flex items-center justify-between p-3 hover:bg-muted/50 transition-colors"
                  >
                    <div className="flex items-center gap-2">
                      <Icon className="h-4 w-4 text-muted-foreground" />
                      <span className="font-medium">{category}</span>
                      <Badge variant="secondary" className="text-xs">
                        {dims.length}
                      </Badge>
                    </div>
                    {isExpanded ? (
                      <ChevronDown className="h-4 w-4 text-muted-foreground" />
                    ) : (
                      <ChevronRight className="h-4 w-4 text-muted-foreground" />
                    )}
                  </button>
                  
                  {isExpanded && (
                    <div className="border-t bg-muted/20 p-3 space-y-2">
                      {dims.map((dim) => (
                        <div
                          key={dim.key}
                          className="bg-background rounded-md p-2 text-sm"
                        >
                          <div className="flex items-center justify-between mb-1">
                            <span className="font-medium">{dim.name}</span>
                            <Badge className={TYPE_BADGES[dim.type] || 'bg-gray-100'}>
                              {dim.type}
                            </Badge>
                          </div>
                          <div className="text-xs text-muted-foreground">
                            <code className="bg-muted px-1 rounded">{dim.key}</code>
                            {dim.examples.length > 0 && (
                              <span className="ml-2">
                                örn: {dim.examples.slice(0, 3).join(', ')}
                              </span>
                            )}
                          </div>
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              );
            })}
          </CardContent>
        </Card>

        {/* Metrics & Verbs */}
        <div className="space-y-6">
          {/* Metrics */}
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <Calculator className="h-5 w-5" />
                Metrics (Metrikler)
              </CardTitle>
            </CardHeader>
            <CardContent>
              <div className="grid gap-2">
                {schema?.metrics.map((metric) => (
                  <div
                    key={metric.key}
                    className="flex items-center justify-between p-2 bg-muted/30 rounded-md"
                  >
                    <div>
                      <span className="font-medium text-sm">{metric.name}</span>
                      <code className="ml-2 text-xs text-muted-foreground bg-muted px-1 rounded">
                        {metric.key}
                      </code>
                    </div>
                    <div className="flex items-center gap-2">
                      <Badge className={TYPE_BADGES[metric.type] || 'bg-gray-100'}>
                        {metric.type}
                      </Badge>
                      <span className="text-xs text-muted-foreground">{metric.unit}</span>
                    </div>
                  </div>
                ))}
              </div>
            </CardContent>
          </Card>

          {/* Verbs */}
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <Wrench className="h-5 w-5" />
                Verbs (İşlem Tipleri)
              </CardTitle>
            </CardHeader>
            <CardContent>
              <div className="grid gap-2">
                {schema?.verbs.map((verb) => (
                  <div
                    key={verb.id}
                    className="p-3 bg-muted/30 rounded-md"
                  >
                    <div className="flex items-center gap-2 mb-1">
                      <Badge variant="outline">{verb.display}</Badge>
                      <code className="text-xs text-muted-foreground">{verb.id}</code>
                    </div>
                    <p className="text-sm text-muted-foreground">{verb.description}</p>
                  </div>
                ))}
              </div>
            </CardContent>
          </Card>

          {/* Example Queries */}
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <MessageSquare className="h-5 w-5" />
                Örnek Sorgular
              </CardTitle>
            </CardHeader>
            <CardContent>
              <div className="space-y-2">
                {schema?.example_queries.map((query, idx) => (
                  <div
                    key={idx}
                    className="p-2 bg-muted/30 rounded-md text-sm flex items-start gap-2"
                  >
                    <span className="text-muted-foreground">{idx + 1}.</span>
                    <span>{query}</span>
                  </div>
                ))}
              </div>
            </CardContent>
          </Card>
        </div>
      </div>
    </div>
  );
}