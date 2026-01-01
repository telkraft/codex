'use client';

import { useEffect } from 'react';
import { useSettingsStore, useLLMConfigStore } from '@/lib/store';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Loader2, Zap, Brain, Database, Server, AlertCircle } from 'lucide-react';

// ============================================================================
// 🆕 FALLBACK DEĞERLERİ (API erişilemezse)
// ============================================================================

const FALLBACK_PROVIDERS = [
  { id: 'local', name: 'Local (Ollama)', icon: '🏠', description: 'Yerel, ücretsiz, gizli' },
  { id: 'groq', name: 'Groq Cloud', icon: '⚡', description: 'LPU, ultra hızlı (~100ms)' },
  { id: 'openrouter', name: 'OpenRouter', icon: '🌐', description: '200+ model (Claude, GPT-4)' },
  { id: 'google', name: 'Google AI', icon: '🔷', description: 'Gemini, 1M context' },
  { id: 'cerebras', name: 'Cerebras', icon: '🧠', description: '2100 token/sn' },
  { id: 'mistral', name: 'Mistral AI', icon: '🌀', description: 'Avrupa lideri, Codestral' },
];

const FALLBACK_MODELS: Record<string, Array<{ value: string; label: string; description: string }>> = {
  local: [
    { value: 'gemma2:2b', label: 'Gemma 2 (2B) • Ultra Hafif', description: 'En hızlı yanıt' },
    { value: 'llama3.1:8b', label: 'Llama 3.1 (8B) • Genel Amaçlı', description: 'Önerilen' },
    { value: 'qwen2.5:7b', label: 'Qwen 2.5 (7B) • Türkçe', description: 'Çok dilli' },
  ],
  groq: [
    { value: 'llama-3.3-70b-versatile', label: 'Llama 3.3 (70B) • Güçlü', description: 'En güncel' },
    { value: 'gemma2-9b-it', label: 'Gemma 2 (9B) • Hızlı', description: 'Dengeli' },
    { value: 'mixtral-8x7b-32768', label: 'Mixtral 8x7B • MoE', description: '32K context' },
  ],
  openrouter: [
    { value: 'anthropic/claude-3.5-sonnet', label: 'Claude 3.5 Sonnet', description: 'En akıllı' },
    { value: 'openai/gpt-4o', label: 'GPT-4o', description: 'Multimodal' },
    { value: 'google/gemini-pro-1.5', label: 'Gemini Pro 1.5', description: '1M context' },
    { value: 'meta-llama/llama-3.1-70b-instruct', label: 'Llama 3.1 (70B)', description: 'Açık kaynak' },
  ],
  google: [
    { value: 'gemini-1.5-flash', label: 'Gemini 1.5 Flash • Hızlı', description: '1M token' },
    { value: 'gemini-1.5-pro', label: 'Gemini 1.5 Pro • Güçlü', description: 'En akıllı' },
    { value: 'gemini-2.0-flash-exp', label: 'Gemini 2.0 Flash • Deneysel', description: 'En yeni' },
  ],
  cerebras: [
    { value: 'llama3.1-8b', label: 'Llama 3.1 (8B) • Ultra Hızlı', description: '2100 token/sn' },
    { value: 'llama3.1-70b', label: 'Llama 3.1 (70B) • Güçlü', description: '450 token/sn' },
    { value: 'llama-3.3-70b', label: 'Llama 3.3 (70B) • En Yeni', description: 'En güncel' },
  ],
  mistral: [
    { value: 'mistral-large-latest', label: 'Mistral Large • Flagship', description: 'En güçlü' },
    { value: 'mistral-small-latest', label: 'Mistral Small • Hızlı', description: 'Düşük latency' },
    { value: 'codestral-latest', label: 'Codestral • Kod Uzmanı', description: 'Kod için' },
    { value: 'open-mixtral-8x22b', label: 'Mixtral 8x22B • MoE', description: '176B parametre' },
  ],
};

const FALLBACK_ROLES = [
  { value: 'servis_analisti', label: '📊 Servis Analisti', description: 'Operasyonel analiz' },
  { value: 'filo_yoneticisi', label: '🚛 Filo Yöneticisi', description: 'Stratejik bakış' },
  { value: 'teknik_uzman', label: '🔧 Teknik Uzman', description: 'Detaylı teknik' },
  { value: 'tedarik_zinciri_uzmani', label: '📦 Tedarik Zinciri', description: 'Lojistik odaklı' },
  { value: 'egitmen', label: '🎓 Eğitmen', description: 'Eğitim odaklı' },
  { value: 'cto', label: '💼 CTO', description: 'Stratejik analiz' },
];

const FALLBACK_BEHAVIORS = [
  { value: 'balanced', label: '⚖️ Dengeli / Analitik', description: 'Önerilen' },
  { value: 'commentary', label: '💬 Yorumlayıcı', description: 'Açıklayıcı' },
  { value: 'predictive', label: '🔮 Öngörüsel', description: 'Senaryo tabanlı' },
  { value: 'report', label: '📄 Rapor Üret', description: 'Yapılandırılmış' },
];

const quickQueries = [
  { label: 'En sık arızalar', query: 'En sık görülen arıza kodları neler?' },
  { label: 'Maliyet analizi', query: 'Malzeme maliyetleri nasıl değişti?' },
  { label: 'Araç istatistikleri', query: 'Araç tiplerinin bakım dağılımı nasıl?' },
  { label: 'Mevsimsel trend', query: 'Mevsimlere göre bakım dağılımı nasıl?' },
];

export function ChatSidebar() {
  const {
    provider,
    model,
    setModel,
    useLLM,
    setUseLLM,
    collection,
    contextLimit,
    setContextLimit,
    role,
    setRole,
    behavior,
    setBehavior,
    switchProvider,
  } = useSettingsStore();

  const {
    providers,
    roles,
    behaviors,
    isConfigLoaded,
    isConfigLoading,
    configError,
    getProviderModels,
    getProviderDefault,
  } = useLLMConfigStore();

  // ─────────────────────────────────────────────────────────────
  // DİNAMİK LİSTELER
  // ─────────────────────────────────────────────────────────────

  // Provider listesi
  const availableProviders = providers.length > 0 
    ? providers 
    : FALLBACK_PROVIDERS.map(p => ({ ...p, models: [], default_model: '' }));

  // Seçili provider'ın modelleri
  const currentProviderModels = isConfigLoaded 
    ? getProviderModels(provider)
    : (FALLBACK_MODELS[provider] || FALLBACK_MODELS.local);

  // Rol listesi
  const availableRoles = roles.length > 0 
    ? roles 
    : FALLBACK_ROLES;

  // Davranış listesi  
  const availableBehaviors = behaviors.length > 0 
    ? behaviors 
    : FALLBACK_BEHAVIORS;

  // ─────────────────────────────────────────────────────────────
  // PROVIDER DEĞİŞTİĞİNDE MODEL GÜNCELLE
  // ─────────────────────────────────────────────────────────────

  const handleProviderChange = (newProvider: string) => {
    const defaultModel = isConfigLoaded 
      ? getProviderDefault(newProvider)
      : (FALLBACK_MODELS[newProvider]?.[0]?.value || '');
    
    switchProvider(newProvider, defaultModel);
  };

  return (
    <div className="w-72 border-r bg-card overflow-auto">
      <div className="p-4 space-y-4">
        {/* Quick Queries */}
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm flex items-center gap-2">
              <Zap className="h-4 w-4" />
              Hızlı Sorgular
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-2">
            {quickQueries.map((item) => (
              <Button
                key={item.label}
                variant="outline"
                size="sm"
                className="w-full justify-start text-xs h-8"
                onClick={() => {
                  const event = new CustomEvent('quickQuery', {
                    detail: item.query,
                  });
                  window.dispatchEvent(event);
                }}
              >
                {item.label}
              </Button>
            ))}
          </CardContent>
        </Card>

        {/* 🆕 Provider Selection */}
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm flex items-center gap-2">
              <Server className="h-4 w-4" />
              LLM Sağlayıcı
              {isConfigLoading && <Loader2 className="h-3 w-3 animate-spin" />}
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-3">
            {/* LLM Toggle */}
            <div className="flex items-center justify-between">
              <span className="text-sm font-medium">LLM Kullan</span>
              <Button
                variant={useLLM ? 'default' : 'outline'}
                size="sm"
                onClick={() => setUseLLM(!useLLM)}
              >
                {useLLM ? 'Açık' : 'Kapalı'}
              </Button>
            </div>

            {/* Config Error Warning */}
            {configError && (
              <div className="flex items-center gap-2 text-xs text-amber-600 dark:text-amber-400">
                <AlertCircle className="h-3 w-3" />
                <span>Fallback mod aktif</span>
              </div>
            )}

            {/* Provider Selection */}
            {useLLM && (
              <div className="space-y-2">
                <label className="text-xs text-muted-foreground font-medium">Sağlayıcı Seçimi</label>
                <div className="space-y-1 max-h-64 overflow-y-auto">
                  {availableProviders.map((p) => (
                    <button
                      key={p.id}
                      className={`w-full text-left p-2 rounded-lg border text-xs transition-colors ${
                        provider === p.id
                          ? 'bg-primary text-primary-foreground border-primary'
                          : 'hover:bg-accent border-border'
                      }`}
                      onClick={() => handleProviderChange(p.id)}
                    >
                      <div className="font-medium flex items-center gap-2">
                        <span>{p.icon}</span>
                        <span>{p.name}</span>
                      </div>
                      {p.description && (
                        <div className={`text-[10px] mt-0.5 ${
                          provider === p.id ? 'text-primary-foreground/80' : 'text-muted-foreground'
                        }`}>
                          {p.description}
                        </div>
                      )}
                    </button>
                  ))}
                </div>
              </div>
            )}
          </CardContent>
        </Card>

        {/* Model Settings */}
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm flex items-center gap-2">
              <Brain className="h-4 w-4" />
              Model Ayarları
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-3">
            {/* Model Selection */}
            {useLLM && (
              <div className="space-y-2">
                <label className="text-xs text-muted-foreground font-medium">
                  Model Seçimi 
                  <span className="ml-1 text-[10px]">({currentProviderModels.length} model)</span>
                </label>
                <div className="space-y-1 max-h-64 overflow-y-auto">
                  {currentProviderModels.map((option) => (
                    <button
                      key={option.value}
                      className={`w-full text-left p-2 rounded-lg border text-xs transition-colors ${
                        model === option.value
                          ? 'bg-primary text-primary-foreground border-primary'
                          : 'hover:bg-accent border-border'
                      }`}
                      onClick={() => setModel(option.value)}
                    >
                      <div className="font-medium">{option.label}</div>
                      {option.description && (
                        <div className={`text-[10px] ${
                          model === option.value ? 'text-primary-foreground/80' : 'text-muted-foreground'
                        }`}>
                          {option.description}
                        </div>
                      )}
                    </button>
                  ))}
                </div>
              </div>
            )}

            {/* Role Selection */}
            {useLLM && (
              <div className="space-y-2">
                <label className="text-xs text-muted-foreground font-medium">Rol</label>
                <div className="space-y-1 max-h-48 overflow-y-auto">
                  {availableRoles.map((option) => (
                    <button
                      key={option.value}
                      className={`w-full text-left p-2 rounded-lg border text-xs transition-colors ${
                        role === option.value
                          ? 'bg-primary text-primary-foreground border-primary'
                          : 'hover:bg-accent border-border'
                      }`}
                      onClick={() => setRole(option.value)}
                    >
                      <div className="font-medium">{option.label}</div>
                      {option.description && (
                        <div className={`text-[10px] ${
                          role === option.value ? 'text-primary-foreground/80' : 'text-muted-foreground'
                        }`}>
                          {option.description}
                        </div>
                      )}
                    </button>
                  ))}
                </div>
              </div>
            )}

            {/* Behavior Selection */}
            {useLLM && (
              <div className="space-y-2">
                <label className="text-xs text-muted-foreground font-medium">Davranış</label>
                <div className="space-y-1">
                  {availableBehaviors.map((option) => (
                    <button
                      key={option.value}
                      className={`w-full text-left p-2 rounded-lg border text-xs transition-colors ${
                        behavior === option.value
                          ? 'bg-primary text-primary-foreground border-primary'
                          : 'hover:bg-accent border-border'
                      }`}
                      onClick={() => setBehavior(option.value)}
                    >
                      <div className="font-medium">{option.label}</div>
                      {option.description && (
                        <div className={`text-[10px] ${
                          behavior === option.value ? 'text-primary-foreground/80' : 'text-muted-foreground'
                        }`}>
                          {option.description}
                        </div>
                      )}
                    </button>
                  ))}
                </div>
              </div>
            )}
          </CardContent>
        </Card>

        {/* RAG Settings */}
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm flex items-center gap-2">
              <Database className="h-4 w-4" />
              RAG Ayarları
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-3">
            {/* Collection */}
            <div className="space-y-1">
              <label className="text-xs text-muted-foreground">Collection</label>
              <Badge variant="outline" className="w-full justify-center text-[10px]">
                {collection}
              </Badge>
            </div>

            {/* Context Limit */}
            <div className="space-y-1">
              <label className="text-xs text-muted-foreground">
                Context Limit: {contextLimit}
              </label>
              <input
                type="range"
                min="1"
                max="20"
                value={contextLimit}
                onChange={(e) => setContextLimit(Number(e.target.value))}
                className="w-full"
              />
            </div>

            {/* Aktif Provider Özeti */}
            {useLLM && (
              <div className="pt-2 border-t">
                <p className="text-[10px] text-muted-foreground">
                  Aktif: {availableProviders.find(p => p.id === provider)?.icon}{' '}
                  {availableProviders.find(p => p.id === provider)?.name || provider}
                </p>
                <p className="text-[10px] text-muted-foreground truncate">
                  Model: {model || 'Seçilmedi'}
                </p>
              </div>
            )}
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
