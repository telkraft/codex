// lib/api.ts
// ============================================================================
// RAG API Client
// ============================================================================
// Tüm API çağrıları tek bir backend'e (rag-api) gider.
// 🆕 LLM Provider config endpoint'leri eklendi.
// 🆕 ChatResponse'a general_chat ve query_executed eklendi.

const RAG_API_URL = process.env.NEXT_PUBLIC_RAG_API_URL || 'https://app.promptever.com/api/rag';

// ============================================================================
// 🆕 LLM CONFIG TYPES
// ============================================================================

export interface ProviderModelInfo {
  value: string;
  label: string;
  description: string;
}

export interface ProviderInfo {
  id: string;
  name: string;
  icon: string;
  description?: string;
  models: ProviderModelInfo[];
  default_model: string;
}

export interface RoleInfo {
  value: string;
  label: string;
  description: string;
}

export interface BehaviorInfo {
  value: string;
  label: string;
  description: string;
}

export interface LLMDefaults {
  provider: string;
  model: string;
  role: string;
  behavior: string;
}

export interface LLMConfigResponse {
  providers: ProviderInfo[];
  roles: RoleInfo[];
  behaviors: BehaviorInfo[];
  defaults: LLMDefaults;
}

// ============================================================================
// CHAT TYPES
// ============================================================================

export interface ChatRequest {
  query: string;
  collection?: string;
  use_llm?: boolean;
  limit?: number;
  provider?: string;  // 🆕 LLM provider
  model?: string;
  role?: string;
  behavior?: string;
}

export interface ChatResponse {
  intent: string;
  scenario?: string;
  answer?: string;
  data?: Record<string, unknown>;
  tables?: Array<{
    title: string;
    description?: string;
    columns: string[];
    rows: Array<Record<string, any>>;
    meta?: Record<string, any>;
  }>;
  statistics?: Record<string, unknown>;
  summary?: string;
  sources?: Array<{
    content: string;
    score: number;
    metadata?: Record<string, unknown>;
  }>;
  llm?: {
    provider?: string;  // 🆕
    model: string;
    answer: string;
    latency_sec: number;
  };
  
  // 🆕 general_chat handling için yeni alanlar
  general_chat?: boolean;     // Genel sohbet mi? (veri sorgusu değil)
  query_executed?: boolean;   // Sorgu çalıştırıldı mı?
  llm_enabled?: boolean;      // LLM kullanıldı mı? (client'tan gelen use_llm değeri)
}

export interface HealthResponse {
  status: string;
  details?: Record<string, string>;
}

export interface LRSStatsResponse {
  data: {
    totalStatements: number;
    uniqueVehicles: number;
    faultCodeRatio: number;
  };
}

// ============================================================================
// QUICK QUERIES TYPES
// ============================================================================

export interface QuickQueryCategory {
  id: string;
  name: string;
  icon: string;
  order: number;
  is_default: boolean;
}

export interface QuickQuery {
  id: string;
  category_id: string;
  text: string;
  description: string;
  tags: string[];
  is_active: boolean;
  order: number;
  source: 'canonical' | 'custom';
  canonical_ref?: string | null;
}

export interface QuickQueriesData {
  version: string;
  last_updated: string;
  categories: QuickQueryCategory[];
  queries: QuickQuery[];
  stats: {
    canonical_count: number;
    custom_count: number;
    total: number;
  };
}

export interface QuickQueriesStats {
  canonical_count: number;
  custom_count: number;
  custom_categories_count: number;
  default_categories_count: number;
  last_updated: string | null;
}

export interface CreateQueryRequest {
  text: string;
  category_id: string;
  description?: string;
  tags?: string[];
  is_active?: boolean;
  order?: number;
}

export interface UpdateQueryRequest {
  text?: string;
  category_id?: string;
  description?: string;
  tags?: string[];
  is_active?: boolean;
  order?: number;
}

export interface CreateCategoryRequest {
  id?: string;
  name: string;
  icon?: string;
  order?: number;
}

// ============================================================================
// API CLIENT CLASS
// ============================================================================

class RagApiClient {
  private baseUrl: string;
  private debug: boolean;

  constructor(baseUrl: string = RAG_API_URL, debug: boolean = true) {
    this.baseUrl = baseUrl;
    this.debug = debug;
  }

  private log(message: string, data?: any) {
    if (this.debug) {
      console.log(`[RAG API] ${message}`, data ? data : '');
    }
  }

  private async request<T>(
    endpoint: string,
    options: RequestInit = {}
  ): Promise<T> {
    const url = `${this.baseUrl}${endpoint}`;
    
    this.log(`📤 Request: ${options.method || 'GET'} ${url}`);
    
    if (options.body) {
      this.log('📦 Payload:', JSON.parse(options.body as string));
    }
    
    const response = await fetch(url, {
      ...options,
      headers: {
        'Content-Type': 'application/json',
        ...options.headers,
      },
    });

    // DELETE için 204 No Content kontrolü
    if (response.status === 204) {
      return {} as T;
    }

    if (!response.ok) {
      const errorText = await response.text();
      this.log(`❌ Error: ${response.status} ${response.statusText}`, errorText);
      throw new Error(`API Error: ${response.status} ${response.statusText}`);
    }

    const data = await response.json();
    this.log('📥 Response:', data);
    
    return data;
  }

  // ─────────────────────────────────────────────────────────────────────────────
  // CORE ENDPOINTS
  // ─────────────────────────────────────────────────────────────────────────────

  async health(): Promise<HealthResponse> {
    return this.request<HealthResponse>('/health');
  }

  async chat(request: ChatRequest): Promise<ChatResponse> {
    const sanitizedRequest: ChatRequest = {
      query: request.query,
      collection: request.collection || 'man_local_service_maintenance',
      use_llm: request.use_llm ?? true,
      limit: request.limit || 100,
      provider: request.provider,  // 🆕
      model: request.model,
      role: request.role || 'servis_analisti',
      behavior: request.behavior || 'balanced',
    };
    
    this.log('🔧 Sanitized Request:', sanitizedRequest);
    
    return this.request<ChatResponse>('/chat', {
      method: 'POST',
      body: JSON.stringify(sanitizedRequest),
    });
  }

  async getLRSStats(): Promise<LRSStatsResponse> {
    return this.request<LRSStatsResponse>('/lrs/stats/general');
  }

  async getCollections(): Promise<string[]> {
    return this.request<string[]>('/collections');
  }

  async getModels(): Promise<string[]> {
    try {
      const response = await this.request<{ models: string[] }>('/models');
      return response.models || [];
    } catch {
      return ['gemma2:2b', 'llama3.1:8b', 'qwen2.5:0.5b'];
    }
  }

  // ─────────────────────────────────────────────────────────────────────────────
  // 🆕 LLM CONFIG ENDPOINTS
  // ─────────────────────────────────────────────────────────────────────────────

  /**
   * Tüm LLM konfigürasyonunu al
   * Providers, roles, behaviors ve defaults içerir
   */
  async getLLMConfig(): Promise<LLMConfigResponse> {
    return this.request<LLMConfigResponse>('/llm/config');
  }

  /**
   * Tüm provider'ları listele
   */
  async getLLMProviders(): Promise<ProviderInfo[]> {
    return this.request<ProviderInfo[]>('/llm/providers');
  }

  /**
   * Belirli bir provider'ın modellerini al
   */
  async getProviderModels(providerId: string): Promise<ProviderModelInfo[]> {
    return this.request<ProviderModelInfo[]>(`/llm/providers/${providerId}/models`);
  }

  /**
   * LLM provider'ların sağlık durumu
   */
  async getLLMHealth(): Promise<Record<string, boolean>> {
    return this.request<Record<string, boolean>>('/llm/health');
  }

  /**
   * Rol listesi
   */
  async getLLMRoles(): Promise<RoleInfo[]> {
    return this.request<RoleInfo[]>('/llm/roles');
  }

  /**
   * Davranış listesi
   */
  async getLLMBehaviors(): Promise<BehaviorInfo[]> {
    return this.request<BehaviorInfo[]>('/llm/behaviors');
  }

  // ─────────────────────────────────────────────────────────────────────────────
  // QUICK QUERIES ENDPOINTS
  // ─────────────────────────────────────────────────────────────────────────────

  /**
   * Tüm sorguları getir
   */
  async getQuickQueries(options?: {
    activeOnly?: boolean;
    categoryId?: string;
    includeCanonical?: boolean;
    includeCustom?: boolean;
  }): Promise<QuickQueriesData> {
    const params = new URLSearchParams();
    
    if (options?.activeOnly) params.append('active_only', 'true');
    if (options?.categoryId) params.append('category_id', options.categoryId);
    if (options?.includeCanonical === false) params.append('include_canonical', 'false');
    if (options?.includeCustom === false) params.append('include_custom', 'false');
    
    const queryString = params.toString();
    const endpoint = `/quick-queries${queryString ? `?${queryString}` : ''}`;
    
    return this.request<QuickQueriesData>(endpoint);
  }

  /**
   * Tüm sorguları getir (alias for backward compatibility)
   */
  async getAll(): Promise<QuickQueriesData> {
    return this.getQuickQueries();
  }

  /**
   * Aktif sorguları getir (chat dropdown için)
   */
  async getActiveQueries(): Promise<QuickQuery[]> {
    return this.request<QuickQuery[]>('/quick-queries/active');
  }

  /**
   * Kategorileri getir
   */
  async getCategories(): Promise<QuickQueryCategory[]> {
    return this.request<QuickQueryCategory[]>('/quick-queries/categories');
  }

  /**
   * İstatistikleri getir
   */
  async getQuickQueriesStats(): Promise<QuickQueriesStats> {
    return this.request<QuickQueriesStats>('/quick-queries/stats');
  }

  /**
   * Tek sorgu getir
   */
  async getQuery(queryId: string): Promise<QuickQuery> {
    return this.request<QuickQuery>(`/quick-queries/${queryId}`);
  }

  /**
   * Yeni custom sorgu oluştur
   */
  async createQuery(query: CreateQueryRequest): Promise<QuickQuery> {
    return this.request<QuickQuery>('/quick-queries', {
      method: 'POST',
      body: JSON.stringify(query),
    });
  }

  /**
   * Custom sorgu güncelle
   */
  async updateQuery(queryId: string, update: UpdateQueryRequest): Promise<QuickQuery> {
    return this.request<QuickQuery>(`/quick-queries/${queryId}`, {
      method: 'PUT',
      body: JSON.stringify(update),
    });
  }

  /**
   * Sorgunun aktif/pasif durumunu değiştir
   */
  async toggleQuery(queryId: string): Promise<QuickQuery> {
    return this.request<QuickQuery>(`/quick-queries/${queryId}/toggle`, {
      method: 'PUT',
    });
  }

  /**
   * Custom sorgu sil
   */
  async deleteQuery(queryId: string): Promise<void> {
    await this.request<void>(`/quick-queries/${queryId}`, {
      method: 'DELETE',
    });
  }

  /**
   * Yeni custom kategori oluştur
   */
  async createCategory(category: CreateCategoryRequest): Promise<QuickQueryCategory> {
    return this.request<QuickQueryCategory>('/quick-queries/categories', {
      method: 'POST',
      body: JSON.stringify(category),
    });
  }

  /**
   * Custom kategori sil
   */
  async deleteCategory(categoryId: string, force: boolean = false): Promise<void> {
    const queryString = force ? '?force=true' : '';
    await this.request<void>(`/quick-queries/categories/${categoryId}${queryString}`, {
      method: 'DELETE',
    });
  }
}

// ============================================================================
// EXPORT
// ============================================================================

export const ragApi = new RagApiClient(RAG_API_URL, true);

// Backward compatibility alias
export const quickQueriesApi = ragApi;

export { RagApiClient };
export default ragApi;
