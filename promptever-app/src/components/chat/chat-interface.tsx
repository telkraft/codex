'use client';

import { useState, useRef, useEffect } from 'react';
import { useSearchParams } from 'next/navigation';
import { useMutation, useQuery } from '@tanstack/react-query';
import { 
  ragApi, 
  quickQueriesApi, 
  ChatRequest, 
  ChatResponse, 
  QuickQuery, 
  QuickQueryCategory,
  LLMConfigResponse,
} from '@/lib/api';
import { useChatStore, useSettingsStore, useLLMConfigStore } from '@/lib/store';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { ChatMessage } from './chat-message';
import { Send, Loader2, Trash2, Zap, ChevronDown } from 'lucide-react';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
  DropdownMenuLabel,
} from '@/components/ui/dropdown-menu';

// Fallback queries - API çalışmazsa kullanılacak
const FALLBACK_QUERIES = [
  'Bakım ve onarım işlemlerinin dağılımı nedir?',
  'Bakım ve onarım işlemlerinin yıllara göre dağılımı nedir?',
  'Bakım ve onarım işlemlerinin mevsimlere göre dağılımı nedir?',
  'Kış mevsiminde en çok hangi malzemeler kullanılıyor?',
  'Son 2 yılda fiyatı en çok artan malzemeler hangileri?',
];

// ============================================================================
// 🆕 6 PROVIDER FALLBACK DEĞERLERİ
// ============================================================================

const FALLBACK_PROVIDERS = [
  { id: 'groq', name: 'Groq Cloud', icon: '⚡', description: 'LPU, ultra hızlı' },
  { id: 'openrouter', name: 'OpenRouter', icon: '🌐', description: '200+ model' },
  { id: 'google', name: 'Google AI', icon: '🔷', description: 'Gemini' },
  { id: 'cerebras', name: 'Cerebras', icon: '🧠', description: 'Ultra hızlı' },
  { id: 'mistral', name: 'Mistral AI', icon: '🌀', description: 'Avrupa lideri' },
  { id: 'local', name: 'Local (Ollama)', icon: '🏠', description: 'Yerel, ücretsiz' },
];

const FALLBACK_MODELS: Record<string, Array<{ value: string; label: string }>> = {
  groq: [
    { value: 'llama-3.3-70b-versatile', label: 'Llama 3.3 (70B) • Güçlü' },
    { value: 'gemma2-9b-it', label: 'Gemma 2 (9B) • Hızlı' },
    { value: 'mixtral-8x7b-32768', label: 'Mixtral 8x7B • MoE' },
  ],
  openrouter: [
    { value: 'anthropic/claude-3.5-sonnet', label: 'Claude 3.5 Sonnet' },
    { value: 'openai/gpt-4o', label: 'GPT-4o' },
    { value: 'google/gemini-pro-1.5', label: 'Gemini Pro 1.5' },
  ],
  google: [
    { value: 'gemini-1.5-flash', label: 'Gemini 1.5 Flash • Hızlı' },
    { value: 'gemini-1.5-pro', label: 'Gemini 1.5 Pro • Güçlü' },
    { value: 'gemini-2.0-flash-exp', label: 'Gemini 2.0 Flash • Deneysel' },
  ],
  cerebras: [
    { value: 'llama3.1-70b', label: 'Llama 3.1 (70B) • Hızlı' },
    { value: 'llama3.1-8b', label: 'Llama 3.1 (8B) • Ultra Hızlı' },
  ],
  mistral: [
    { value: 'mistral-large-latest', label: 'Mistral Large • Flagship' },
    { value: 'mistral-small-latest', label: 'Mistral Small • Hızlı' },
    { value: 'codestral-latest', label: 'Codestral • Kod Uzmanı' },
  ],
  local: [
    { value: 'gemma2:2b', label: 'Gemma 2 (2B) • Ultra Hafif' },
    { value: 'llama3.1:8b', label: 'Llama 3.1 (8B) • Genel' },
    { value: 'qwen2.5:7b', label: 'Qwen 2.5 (7B) • Türkçe' },
  ],
};

const FALLBACK_ROLES = [
  { value: 'servis_analisti', label: 'Servis Analisti' },
  { value: 'filo_yoneticisi', label: 'Filo Yöneticisi' },
  { value: 'teknik_uzman', label: 'Teknik Uzman' },
];

const FALLBACK_BEHAVIORS = [
  { value: 'balanced', label: 'Dengeli / Analitik' },
  { value: 'commentary', label: 'Yorumlayıcı' },
  { value: 'predictive', label: 'Öngörüsel' },
];

export function ChatInterface() {
  const [input, setInput] = useState('');
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const searchParams = useSearchParams();
  const initialQueryProcessed = useRef(false);
  
  const { messages, addMessage, clearMessages, isLoading, setLoading } = useChatStore();
  const { 
    provider, 
    setProvider, 
    model, 
    setModel, 
    useLLM, 
    setUseLLM, 
    collection, 
    contextLimit, 
    role, 
    setRole, 
    behavior, 
    setBehavior,
    switchProvider,
    initFromDefaults,
  } = useSettingsStore();
  
  const {
    providers,
    roles,
    behaviors,
    defaults,
    isConfigLoaded,
    setLLMConfig,
    setConfigLoading,
    setConfigError,
    getProviderModels,
    getProviderDefault,
  } = useLLMConfigStore();

  // ─────────────────────────────────────────────────────────────
  // 🆕 LLM CONFIG - Sunucudan çek
  // ─────────────────────────────────────────────────────────────
  
  const { data: llmConfigData, isLoading: isLoadingConfig } = useQuery({
    queryKey: ['llm-config'],
    queryFn: async () => {
      setConfigLoading(true);
      try {
        const config = await ragApi.getLLMConfig();
        setLLMConfig(config);
        
        // İlk yüklemede defaults ile initialize et
        if (config.defaults) {
          initFromDefaults(config.defaults);
        }
        
        return config;
      } catch (error) {
        console.warn('LLM config yüklenemedi, fallback kullanılıyor:', error);
        setConfigError('LLM config yüklenemedi');
        return null;
      } finally {
        setConfigLoading(false);
      }
    },
    staleTime: 300000, // 5 dakika cache
    retry: 2,
  });

  // ─────────────────────────────────────────────────────────────
  // QUICK QUERIES - Sunucudan çek
  // ─────────────────────────────────────────────────────────────
  
  const { data: quickQueriesData, isLoading: isLoadingQueries } = useQuery({
    queryKey: ['quick-queries-active'],
    queryFn: async () => {
      try {
        const data = await quickQueriesApi.getAll();
        return data;
      } catch (error) {
        console.warn('Quick queries yüklenemedi, fallback kullanılıyor:', error);
        return null;
      }
    },
    staleTime: 60000, // 1 dakika cache
    retry: 1,
  });

  // Kategorilere göre grupla ve aktif olanları filtrele
  const groupedQueries = quickQueriesData ? (() => {
    const categories = quickQueriesData.categories.sort((a, b) => a.order - b.order);
    const activeQueries = quickQueriesData.queries.filter(q => q.is_active);
    
    return categories.map(cat => ({
      category: cat,
      queries: activeQueries
        .filter(q => q.category_id === cat.id)
        .sort((a, b) => a.order - b.order)
    })).filter(group => group.queries.length > 0);
  })() : [];

  // Fallback: API çalışmazsa flat liste
  const flatQueries = quickQueriesData 
    ? quickQueriesData.queries.filter(q => q.is_active).map(q => q.text)
    : FALLBACK_QUERIES;

  // ─────────────────────────────────────────────────────────────
  // 🆕 DİNAMİK LİSTELER (6 PROVIDER)
  // ─────────────────────────────────────────────────────────────

  // Provider listesi (config'den veya fallback)
  const availableProviders = providers.length > 0 
    ? providers 
    : FALLBACK_PROVIDERS.map(p => ({ ...p, models: [], default_model: '' }));

  // Seçili provider'ın modelleri
  const currentProviderModels = isConfigLoaded 
    ? getProviderModels(provider)
    : (FALLBACK_MODELS[provider] || FALLBACK_MODELS.local)
        .map(m => ({ ...m, description: '' }));

  // Rol listesi
  const availableRoles = roles.length > 0 
    ? roles 
    : FALLBACK_ROLES.map(r => ({ ...r, description: '' }));

  // Davranış listesi  
  const availableBehaviors = behaviors.length > 0 
    ? behaviors 
    : FALLBACK_BEHAVIORS.map(b => ({ ...b, description: '' }));

  // ─────────────────────────────────────────────────────────────
  // 🆕 PROVIDER DEĞİŞTİĞİNDE MODEL GÜNCELLE
  // ─────────────────────────────────────────────────────────────

  const handleProviderChange = (newProvider: string) => {
    const defaultModel = isConfigLoaded 
      ? getProviderDefault(newProvider)
      : (FALLBACK_MODELS[newProvider]?.[0]?.value || '');
    
    switchProvider(newProvider, defaultModel);
  };

  // Scroll to bottom
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  // Chat mutation
  const chatMutation = useMutation({
    mutationFn: async (query: string) => {
      const startTime = Date.now();
      
      const effectiveRole = role || 'servis_analisti';
      const effectiveBehavior = behavior || 'balanced';
      const effectiveProvider = provider || 'local';
      
      const request: ChatRequest = {
        query,
        collection,
        use_llm: useLLM,
        limit: contextLimit,
        provider: useLLM ? effectiveProvider : undefined,
        model: useLLM ? model : undefined,
        role: effectiveRole,
        behavior: effectiveBehavior,
      };
      
      const response = await ragApi.chat(request);
      
      return {
        response,
        elapsed: Date.now() - startTime,
        originalQuery: query,
        // 🆕 useLLM durumunu da taşı
        usedLLM: useLLM,
      };
    },
    onMutate: async (query) => {
      setLoading(true);
      addMessage({
        role: 'user',
        content: query,
      });
    },
    onSuccess: ({ response, elapsed, originalQuery, usedLLM }) => {
      // 🆕 Response'dan veya tables[0].meta'dan general_chat bilgilerini al
      // Backend değerleri bazen meta içinde gönderiyor
      const meta = response.tables?.[0]?.meta || {};
      const isGeneralChat = response.general_chat === true || meta.general_chat === true;
      const queryExecuted = (response.query_executed ?? meta.query_executed) !== false;
      const llmWasActuallyUsed = !!response.llm;

      addMessage({
        role: 'assistant',
        content: response.answer || response.summary || 'Yanıt alındı',
        intent: response.intent,
        scenario: response.scenario,
        data: response.data as Record<string, any> | undefined,
        tables: response.tables,
        sources: response.sources as Array<{
          content: string;
          score: number;
          metadata?: Record<string, any>;
        }> | undefined,
        // 🔧 Provider/model sadece LLM kullanıldıysa
        provider: llmWasActuallyUsed ? (response.llm?.provider || provider) : undefined,
        model: llmWasActuallyUsed ? response.llm?.model : undefined,
        elapsed: response.llm?.latency_sec ?? (elapsed / 1000),
        llmUsed: llmWasActuallyUsed,
        llmAnswer: response.llm?.answer,
        llmRole: llmWasActuallyUsed ? role : undefined,
        llmBehavior: llmWasActuallyUsed ? behavior : undefined,
        originalQuery,
        // 🆕 Yeni alanlar
        generalChat: isGeneralChat,
        queryExecuted: queryExecuted,
      });
    },
    onError: (error) => {
      addMessage({
        role: 'assistant',
        content: `Hata oluştu: ${error.message}`,
        intent: 'error',
      });
    },
    onSettled: () => {
      setLoading(false);
    },
  });

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (input.trim() && !isLoading) {
      chatMutation.mutate(input.trim());
      setInput('');
    }
  };

  const handleQuickQuery = (query: string) => {
    if (!isLoading) {
      chatMutation.mutate(query);
    }
  };

  // URL'den gelen sorguyu işle
  useEffect(() => {
    const queryParam = searchParams.get('q');
    if (queryParam && !initialQueryProcessed.current) {
      initialQueryProcessed.current = true;
      chatMutation.mutate(queryParam);
    }
  }, [searchParams]);

  // Aktif provider bilgisi
  const activeProvider = availableProviders.find(p => p.id === provider) 
    || FALLBACK_PROVIDERS.find(p => p.id === provider)
    || { id: provider, name: provider, icon: '🤖' };

  // Aktif rol ve davranış için label
  const activeRoleLabel = availableRoles.find(r => r.value === role)?.label || role;
  const activeBehaviorLabel = availableBehaviors.find(b => b.value === behavior)?.label || behavior;

  return (
    <div className="flex h-full flex-col">
      {/* Header Bar - Sohbeti Temizle Butonu */}
      {messages.length > 0 && (
        <div className="flex items-center justify-end border-b px-4 py-2 bg-muted/30">
          <Button
            variant="ghost"
            size="sm"
            onClick={clearMessages}
            className="text-muted-foreground hover:text-destructive"
            title="Tüm sohbet geçmişini sil"
          >
            <Trash2 className="h-4 w-4 mr-2" />
            Sohbeti Temizle
          </Button>
        </div>
      )}

      {/* Messages */}
      <div className="flex-1 overflow-auto p-4 space-y-4">
        {messages.length === 0 ? (
          <div className="flex h-full items-center justify-center text-center">
            <div>
              <div className="rounded-full bg-primary/10 p-4 mb-4 inline-block">
                <Send className="h-8 w-8 text-primary" />
              </div>
              <h2 className="text-xl font-semibold mb-2">
                Promptever RAG Chat
              </h2>
              <p className="text-muted-foreground max-w-md">
                Servis bakım verilerinizi analiz etmek için sorularınızı yazın
              </p>
              {isLoadingConfig && (
                <p className="text-xs text-muted-foreground mt-2">
                  <Loader2 className="h-3 w-3 animate-spin inline mr-1" />
                  LLM ayarları yükleniyor...
                </p>
              )}
              {/* 🆕 Provider özeti */}
              {!isLoadingConfig && availableProviders.length > 0 && (
                <p className="text-xs text-muted-foreground mt-3">
                  {availableProviders.length} LLM provider kullanılabilir
                </p>
              )}
            </div>
          </div>
        ) : (
          <>
            {messages.map((message) => (
              <ChatMessage key={message.id} message={message} />
            ))}
            {/* 🔧 FIX: Loading mesajı - LLM durumuna göre farklı göster */}
            {isLoading && (
              <div className="flex items-center gap-2 text-muted-foreground">
                <Loader2 className="h-4 w-4 animate-spin" />
                <span className="text-sm">
                  {useLLM ? (
                    // LLM açıkken provider adını göster
                    <>{activeProvider.icon} {activeProvider.name} düşünüyor...</>
                  ) : (
                    // LLM kapalıyken sadece "İşleniyor" göster
                    <>Sorgu işleniyor...</>
                  )}
                </span>
              </div>
            )}
            <div ref={messagesEndRef} />
          </>
        )}
      </div>

      {/* Input + Settings */}
      <div className="border-t p-4 space-y-3">
        {/* Input Row */}
        <form onSubmit={handleSubmit} className="flex gap-2">
          <Input
            value={input}
            onChange={(e) => setInput(e.target.value)}
            placeholder="Sorunuzu yazın..."
            disabled={isLoading}
            className="flex-1"
          />
          
          {/* Quick Queries - Kategorili Dropdown */}
          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <Button 
                type="button" 
                variant="outline" 
                size="icon" 
                title="Referans Sorgular"
                disabled={isLoadingQueries}
              >
                {isLoadingQueries ? (
                  <Loader2 className="h-4 w-4 animate-spin" />
                ) : (
                  <Zap className="h-4 w-4" />
                )}
              </Button>
            </DropdownMenuTrigger>
            <DropdownMenuContent align="end" className="w-96 max-h-[70vh] overflow-y-auto">
              {groupedQueries.length > 0 ? (
                // Kategorili görünüm
                groupedQueries.map((group, groupIdx) => (
                  <div key={group.category.id}>
                    {groupIdx > 0 && <DropdownMenuSeparator />}
                    <DropdownMenuLabel className="flex items-center gap-2">
                      <span>{group.category.icon}</span>
                      <span>{group.category.name}</span>
                      <span className="text-xs text-muted-foreground">
                        ({group.queries.length})
                      </span>
                    </DropdownMenuLabel>
                    {group.queries.map((query) => (
                      <DropdownMenuItem
                        key={query.id}
                        onClick={() => handleQuickQuery(query.text)}
                        className="text-xs cursor-pointer py-2 px-4"
                      >
                        <span className="line-clamp-2">{query.text}</span>
                      </DropdownMenuItem>
                    ))}
                  </div>
                ))
              ) : (
                // Fallback - flat liste
                flatQueries.map((query, idx) => (
                  <DropdownMenuItem
                    key={idx}
                    onClick={() => handleQuickQuery(query)}
                    className="text-xs cursor-pointer"
                  >
                    {query}
                  </DropdownMenuItem>
                ))
              )}
              
              {/* Yönetim linki */}
              <DropdownMenuSeparator />
              <DropdownMenuItem asChild className="text-xs text-muted-foreground">
                <a href="/quick-queries" className="flex items-center gap-2">
                  <span>⚙️</span>
                  <span>Sorguları Yönet</span>
                </a>
              </DropdownMenuItem>
            </DropdownMenuContent>
          </DropdownMenu>

          {/* Send */}
          <Button type="submit" disabled={isLoading || !input.trim()}>
            {isLoading ? (
              <Loader2 className="h-4 w-4 animate-spin" />
            ) : (
              <Send className="h-4 w-4" />
            )}
          </Button>
        </form>

        {/* Settings Row - 🆕 6 Provider için güncellendi */}
        <div className="grid grid-cols-2 md:grid-cols-5 gap-2 text-xs">
          {/* LLM Toggle */}
          <label className="flex items-center gap-2 cursor-pointer">
            <input
              type="checkbox"
              checked={useLLM}
              onChange={(e) => setUseLLM(e.target.checked)}
              className="rounded"
            />
            <span className="font-medium">LLM Kullan</span>
          </label>

          {/* 🆕 Provider - 6 seçenek */}
          <Select 
            value={provider} 
            onValueChange={handleProviderChange} 
            disabled={!useLLM}
          >
            <SelectTrigger className="h-8">
              <SelectValue placeholder="Sağlayıcı" />
            </SelectTrigger>
            <SelectContent>
              {availableProviders.map((p) => (
                <SelectItem key={p.id} value={p.id} className="text-xs">
                  <span className="flex items-center gap-2">
                    <span>{p.icon}</span>
                    <span>{p.name}</span>
                  </span>
                </SelectItem>
              ))}
            </SelectContent>
          </Select>

          {/* Model (Provider'a göre dinamik) */}
          <Select value={model} onValueChange={setModel} disabled={!useLLM}>
            <SelectTrigger className="h-8">
              <SelectValue placeholder="Model" />
            </SelectTrigger>
            <SelectContent>
              {currentProviderModels.map((m) => (
                <SelectItem key={m.value} value={m.value} className="text-xs">
                  {m.label}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>

          {/* Role (Sunucudan dinamik) */}
          <Select value={role || 'servis_analisti'} onValueChange={setRole} disabled={!useLLM}>
            <SelectTrigger className="h-8">
              <SelectValue placeholder="Rol" />
            </SelectTrigger>
            <SelectContent>
              {availableRoles.map((r) => (
                <SelectItem key={r.value} value={r.value} className="text-xs">
                  {r.label}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>

          {/* Behavior (Sunucudan dinamik) */}
          <Select value={behavior || 'balanced'} onValueChange={setBehavior} disabled={!useLLM}>
            <SelectTrigger className="h-8">
              <SelectValue placeholder="Davranış" />
            </SelectTrigger>
            <SelectContent>
              {availableBehaviors.map((b) => (
                <SelectItem key={b.value} value={b.value} className="text-xs">
                  {b.label}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>

        {/* Info Footer */}
        <p className="text-xs text-muted-foreground text-center">
          Collection: {collection} • Context: {contextLimit}
          {/* 🔧 FIX: Provider/Rol/Davranış bilgisi sadece LLM açıkken */}
          {useLLM && (
            <>
              {' '}• {activeProvider.icon} {activeProvider.name}
              {' '}• 🎭 {activeRoleLabel} • ✨ {activeBehaviorLabel}
            </>
          )}
        </p>
      </div>
    </div>
  );
}
