import { create } from 'zustand';
import { persist } from 'zustand/middleware';
import type { 
  ProviderInfo, 
  ProviderModelInfo, 
  RoleInfo, 
  BehaviorInfo,
  LLMDefaults 
} from './api';

export interface Message {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  intent?: string;
  scenario?: string;
  data?: Record<string, any>;
  tables?: Array<{
    title: string;
    description?: string;
    columns: string[];
    rows: Array<Record<string, any>>;
    meta?: Record<string, any>;
  }>;
  sources?: Array<{
    content: string;
    score: number;
    metadata?: Record<string, any>;
  }>;
  provider?: string;  // 🆕 LLM provider
  model?: string;
  elapsed?: number;
  llmUsed?: boolean;
  llmAnswer?: string;
  llmRole?: string;
  llmBehavior?: string;
  timestamp: Date;
  originalQuery?: string;
  
  // 🆕 general_chat handling için yeni alanlar
  generalChat?: boolean;      // Sunucudan gelen general_chat değeri
  queryExecuted?: boolean;    // Sunucudan gelen query_executed değeri
}

interface ChatState {
  messages: Message[];
  isLoading: boolean;
  addMessage: (message: Omit<Message, 'id' | 'timestamp'>) => void;
  clearMessages: () => void;
  setLoading: (loading: boolean) => void;
}

export const useChatStore = create<ChatState>()(
  persist(
    (set) => ({
      messages: [],
      isLoading: false,
      addMessage: (message) =>
        set((state) => ({
          messages: [
            ...state.messages,
            {
              ...message,
              id: Math.random().toString(36).substring(7),
              timestamp: new Date(),
            },
          ],
        })),
      clearMessages: () => set({ messages: [] }),
      setLoading: (loading) => set({ isLoading: loading }),
    }),
    {
      name: 'chat-storage',
    }
  )
);

// ============================================================================
// 🆕 LLM CONFIG STORE
// ============================================================================

interface LLMConfigState {
  // Server'dan gelen config
  providers: ProviderInfo[];
  roles: RoleInfo[];
  behaviors: BehaviorInfo[];
  defaults: LLMDefaults | null;
  
  // Config yüklenme durumu
  isConfigLoaded: boolean;
  isConfigLoading: boolean;
  configError: string | null;
  
  // Actions
  setLLMConfig: (config: {
    providers: ProviderInfo[];
    roles: RoleInfo[];
    behaviors: BehaviorInfo[];
    defaults: LLMDefaults;
  }) => void;
  setConfigLoading: (loading: boolean) => void;
  setConfigError: (error: string | null) => void;
  
  // Helper: Belirli provider'ın modellerini al
  getProviderModels: (providerId: string) => ProviderModelInfo[];
  getProviderDefault: (providerId: string) => string;
}

export const useLLMConfigStore = create<LLMConfigState>()((set, get) => ({
  providers: [],
  roles: [],
  behaviors: [],
  defaults: null,
  isConfigLoaded: false,
  isConfigLoading: false,
  configError: null,
  
  setLLMConfig: (config) => set({
    providers: config.providers,
    roles: config.roles,
    behaviors: config.behaviors,
    defaults: config.defaults,
    isConfigLoaded: true,
    configError: null,
  }),
  
  setConfigLoading: (loading) => set({ isConfigLoading: loading }),
  
  setConfigError: (error) => set({ 
    configError: error,
    isConfigLoading: false,
  }),
  
  getProviderModels: (providerId) => {
    const provider = get().providers.find(p => p.id === providerId);
    return provider?.models || [];
  },
  
  getProviderDefault: (providerId) => {
    const provider = get().providers.find(p => p.id === providerId);
    return provider?.default_model || '';
  },
}));

// ============================================================================
// SETTINGS STORE (GÜNCELLEME: provider eklendi)
// ============================================================================

interface SettingsState {
  // 🆕 Provider (local, groq)
  provider: string;
  model: string;
  useLLM: boolean;
  collection: string;
  contextLimit: number;
  role: string;
  behavior: string;
  showDebug: boolean;
  
  // Actions
  setProvider: (provider: string) => void;
  setModel: (model: string) => void;
  setUseLLM: (use: boolean) => void;
  setCollection: (collection: string) => void;
  setContextLimit: (limit: number) => void;
  setRole: (role: string) => void;
  setBehavior: (behavior: string) => void;
  setShowDebug: (show: boolean) => void;
  
  // 🆕 Provider değiştiğinde modeli de güncelle
  switchProvider: (providerId: string, defaultModel?: string) => void;
  
  // 🆕 Server defaults'tan initialize et
  initFromDefaults: (defaults: LLMDefaults) => void;
}

export const useSettingsStore = create<SettingsState>()(
  persist(
    (set, get) => ({
      provider: 'groq',  // 🆕 Default provider
      model: 'llama-3.3-70b-versatile',
      useLLM: true,
      collection: 'man_local_service_maintenance',
      contextLimit: 100,
      role: 'servis_analisti',
      behavior: 'balanced',
      showDebug: false,
      
      setProvider: (provider) => set({ provider }),
      setModel: (model) => set({ model }),
      setUseLLM: (useLLM) => set({ useLLM }),
      setCollection: (collection) => set({ collection }),
      setContextLimit: (contextLimit) => set({ contextLimit }),
      setRole: (role) => set({ role }),
      setBehavior: (behavior) => set({ behavior }),
      setShowDebug: (showDebug) => set({ showDebug }),
      
      // 🆕 Provider değiştiğinde modeli de sıfırla
      switchProvider: (providerId, defaultModel) => {
        set({
          provider: providerId,
          model: defaultModel || '',  // Model, LLMConfig'den alınacak
        });
      },
      
      // 🆕 Server defaults ile initialize
      initFromDefaults: (defaults) => {
        const current = get();
        // Sadece ilk yüklemede veya değerler boşsa set et
        // Kullanıcının mevcut seçimlerini ezme
        set({
          provider: current.provider || defaults.provider,
          model: current.model || defaults.model,
          role: current.role || defaults.role,
          behavior: current.behavior || defaults.behavior,
        });
      },
    }),
    {
      name: 'settings-storage',
      version: 2,  // 🆕 Version artırıldı (provider eklendi)
      migrate: (persistedState: any, version: number) => {
        if (persistedState) {
          // v1 -> v2: provider alanı ekle
          if (!persistedState.provider) {
            persistedState.provider = 'local';
          }
          // Eksik alanlar için varsayılan değerler
          if (!persistedState.role) {
            persistedState.role = 'servis_analisti';
          }
          if (!persistedState.behavior) {
            persistedState.behavior = 'balanced';
          }
        }
        return persistedState;
      },
    }
  )
);

// ============================================================================
// UI STORE
// ============================================================================

interface UIState {
  sidebarOpen: boolean;
  toggleSidebar: () => void;
}

export const useUIStore = create<UIState>()((set) => ({
  sidebarOpen: true,
  toggleSidebar: () => set((state) => ({ sidebarOpen: !state.sidebarOpen })),
}));
