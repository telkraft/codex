'use client';

import { useState, useEffect } from 'react';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { useSettingsStore } from '@/lib/store';
import { Settings, Bug, Database, Brain, RotateCcw, CheckCircle, XCircle } from 'lucide-react';

export default function SettingsPage() {
  const {
    model,
    setModel,
    useLLM,
    setUseLLM,
    collection,
    setCollection,
    contextLimit,
    setContextLimit,
    role,
    setRole,
    behavior,
    setBehavior,
    showDebug,
    setShowDebug,
  } = useSettingsStore();

  const [apiStatus, setApiStatus] = useState<'checking' | 'connected' | 'error'>('checking');
  const [healthData, setHealthData] = useState<any>(null);

  const apiUrl = 'https://app.promptever.com/api/rag';

  const checkHealth = async () => {
    setApiStatus('checking');
    try {
      const res = await fetch(`${apiUrl}/health`);
      const data = await res.json();
      setHealthData(data);
      setApiStatus(data.status === 'ok' || data.status === 'healthy' ? 'connected' : 'error');
    } catch (error) {
      setHealthData({ error: String(error) });
      setApiStatus('error');
    }
  };

  useEffect(() => {
    checkHealth();
  }, []);

  const resetSettings = () => {
    setModel('gemma2:2b');
    setUseLLM(true);
    setCollection('man_local_service_maintenance');
    setContextLimit(100);
    setRole('servis_analisti');
    setBehavior('balanced');
    setShowDebug(false);
  };

  return (
    <div className="container mx-auto p-6 space-y-6">
      <div className="flex items-center gap-3 mb-6">
        <Settings className="h-8 w-8 text-primary" />
        <div>
          <h1 className="text-2xl font-bold">Ayarlar</h1>
          <p className="text-muted-foreground">Uygulama ve debug ayarlarını yönetin</p>
        </div>
      </div>

      <div className="grid gap-6 md:grid-cols-2">
        {/* Debug Settings */}
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Bug className="h-5 w-5" />
              Debug Ayarları
            </CardTitle>
            <CardDescription>
              Geliştirici araçları ve hata ayıklama
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="flex items-center justify-between">
              <div>
                <p className="font-medium">Debug Panelini Göster</p>
                <p className="text-sm text-muted-foreground">
                  Mesajlarda meta/plan bilgisini göster
                </p>
              </div>
              <Button
                variant={showDebug ? 'default' : 'outline'}
                onClick={() => setShowDebug(!showDebug)}
              >
                {showDebug ? 'Açık' : 'Kapalı'}
              </Button>
            </div>
          </CardContent>
        </Card>

        {/* API Status */}
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              {apiStatus === 'connected' ? (
                <CheckCircle className="h-5 w-5 text-green-500" />
              ) : apiStatus === 'error' ? (
                <XCircle className="h-5 w-5 text-red-500" />
              ) : (
                <Database className="h-5 w-5 animate-pulse" />
              )}
              API Durumu
            </CardTitle>
            <CardDescription>
              Backend bağlantı durumu
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="flex items-center justify-between">
              <div>
                <p className="font-medium">
                  {apiStatus === 'connected' && '✅ RAG API: Çalışıyor'}
                  {apiStatus === 'error' && '❌ RAG API: Bağlantı hatası'}
                  {apiStatus === 'checking' && '⏳ Kontrol ediliyor...'}
                </p>
                <p className="text-sm text-muted-foreground">{apiUrl}</p>
              </div>
              <Button variant="outline" size="sm" onClick={checkHealth}>
                Test Et
              </Button>
            </div>

            {healthData && (
              <pre className="text-xs bg-muted p-2 rounded overflow-auto max-h-32">
                {JSON.stringify(healthData, null, 2)}
              </pre>
            )}
          </CardContent>
        </Card>

        {/* LLM Settings */}
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Brain className="h-5 w-5" />
              LLM Ayarları
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-3">
            <div className="grid grid-cols-2 gap-2 text-sm">
              <span className="text-muted-foreground">Model:</span>
              <span className="font-medium">{model}</span>
              <span className="text-muted-foreground">LLM:</span>
              <span className="font-medium">{useLLM ? 'Açık' : 'Kapalı'}</span>
              <span className="text-muted-foreground">Rol:</span>
              <span className="font-medium">{role}</span>
              <span className="text-muted-foreground">Davranış:</span>
              <span className="font-medium">{behavior}</span>
            </div>
          </CardContent>
        </Card>

        {/* RAG Settings */}
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Database className="h-5 w-5" />
              RAG Ayarları
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-3">
            <div className="grid grid-cols-2 gap-2 text-sm">
              <span className="text-muted-foreground">Collection:</span>
              <span className="font-medium text-xs">{collection}</span>
              <span className="text-muted-foreground">Context Limit:</span>
              <span className="font-medium">{contextLimit}</span>
            </div>
          </CardContent>
        </Card>

        {/* Reset */}
        <Card className="md:col-span-2">
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <RotateCcw className="h-5 w-5" />
              Sıfırla
            </CardTitle>
          </CardHeader>
          <CardContent>
            <Button variant="destructive" onClick={resetSettings}>
              Tüm Ayarları Varsayılana Döndür
            </Button>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}