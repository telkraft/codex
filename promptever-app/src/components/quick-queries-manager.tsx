'use client';

import React, { useState, useEffect } from 'react';
import ragApi, { QuickQuery, QuickQueryCategory, QuickQueriesData, QuickQueriesStats } from '@/lib/api';

// ============================================================================
// TYPES
// ============================================================================

interface FilterState {
  search: string;
  categoryId: string;
  showInactive: boolean;
  sourceFilter: 'all' | 'canonical' | 'custom';
}

// ============================================================================
// MAIN COMPONENT
// ============================================================================

export default function QuickQueriesManager() {
  // State
  const [data, setData] = useState<QuickQueriesData | null>(null);
  const [stats, setStats] = useState<QuickQueriesStats | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  
  const [filters, setFilters] = useState<FilterState>({
    search: '',
    categoryId: '',
    showInactive: false,
    sourceFilter: 'all',
  });

  // Form state for new query
  const [showAddForm, setShowAddForm] = useState(false);
  const [newQuery, setNewQuery] = useState({
    text: '',
    category_id: 'custom',
    description: '',
    tags: '',
  });
  const [saving, setSaving] = useState(false);

  // ─────────────────────────────────────────────────────────────────────────
  // DATA FETCHING
  // ─────────────────────────────────────────────────────────────────────────

  const fetchData = async () => {
    try {
      setLoading(true);
      setError(null);
      
      const [queriesData, statsData] = await Promise.all([
        ragApi.getQuickQueries(),
        ragApi.getQuickQueriesStats(),
      ]);
      
      setData(queriesData);
      setStats(statsData);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Veriler yüklenemedi');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchData();
  }, []);

  // ─────────────────────────────────────────────────────────────────────────
  // FILTERING
  // ─────────────────────────────────────────────────────────────────────────

  const filteredQueries = React.useMemo(() => {
    if (!data) return [];
    
    return data.queries.filter((query) => {
      // Search filter
      if (filters.search) {
        const searchLower = filters.search.toLowerCase();
        const matchesSearch = 
          query.text.toLowerCase().includes(searchLower) ||
          query.description.toLowerCase().includes(searchLower) ||
          query.tags.some(t => t.toLowerCase().includes(searchLower));
        if (!matchesSearch) return false;
      }
      
      // Category filter
      if (filters.categoryId && query.category_id !== filters.categoryId) {
        return false;
      }
      
      // Active filter
      if (!filters.showInactive && !query.is_active) {
        return false;
      }
      
      // Source filter
      if (filters.sourceFilter !== 'all' && query.source !== filters.sourceFilter) {
        return false;
      }
      
      return true;
    });
  }, [data, filters]);

  // Group by category
  const groupedQueries = React.useMemo(() => {
    const groups: Record<string, QuickQuery[]> = {};
    
    for (const query of filteredQueries) {
      if (!groups[query.category_id]) {
        groups[query.category_id] = [];
      }
      groups[query.category_id].push(query);
    }
    
    return groups;
  }, [filteredQueries]);

  // ─────────────────────────────────────────────────────────────────────────
  // ACTIONS
  // ─────────────────────────────────────────────────────────────────────────

  const handleAddQuery = async (e: React.FormEvent) => {
    e.preventDefault();
    
    if (!newQuery.text.trim()) {
      alert('Sorgu metni zorunludur');
      return;
    }
    
    try {
      setSaving(true);
      
      await ragApi.createQuery({
        text: newQuery.text.trim(),
        category_id: newQuery.category_id,
        description: newQuery.description.trim(),
        tags: newQuery.tags.split(',').map(t => t.trim()).filter(Boolean),
      });
      
      setNewQuery({ text: '', category_id: 'custom', description: '', tags: '' });
      setShowAddForm(false);
      fetchData();
    } catch (err) {
      alert(err instanceof Error ? err.message : 'Sorgu eklenemedi');
    } finally {
      setSaving(false);
    }
  };

  const handleToggleQuery = async (queryId: string) => {
    try {
      await ragApi.toggleQuery(queryId);
      fetchData();
    } catch (err) {
      alert(err instanceof Error ? err.message : 'İşlem başarısız');
    }
  };

  const handleDeleteQuery = async (queryId: string) => {
    if (!confirm('Bu sorguyu silmek istediğinizden emin misiniz?')) {
      return;
    }
    
    try {
      await ragApi.deleteQuery(queryId);
      fetchData();
    } catch (err) {
      alert(err instanceof Error ? err.message : 'Silme başarısız');
    }
  };

  // ─────────────────────────────────────────────────────────────────────────
  // HELPERS
  // ─────────────────────────────────────────────────────────────────────────

  const getCategoryName = (categoryId: string): string => {
    const category = data?.categories.find(c => c.id === categoryId);
    return category ? `${category.icon} ${category.name}` : categoryId;
  };

  // ─────────────────────────────────────────────────────────────────────────
  // RENDER
  // ─────────────────────────────────────────────────────────────────────────

  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-[400px]">
        <div className="text-center">
          <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600 mx-auto mb-4"></div>
          <p className="text-gray-600">Yükleniyor...</p>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="p-6 bg-red-50 border border-red-200 rounded-lg">
        <h3 className="text-red-800 font-medium mb-2">Hata</h3>
        <p className="text-red-600">{error}</p>
        <button
          onClick={fetchData}
          className="mt-4 px-4 py-2 bg-red-600 text-white rounded hover:bg-red-700"
        >
          Tekrar Dene
        </button>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Referans Sorgular</h1>
          <p className="text-sm text-gray-500 mt-1">
            {stats && (
              <>
                {stats.canonical_count} referans, {stats.custom_count} özel sorgu
              </>
            )}
          </p>
        </div>
        
        <button
          onClick={() => setShowAddForm(true)}
          className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 flex items-center gap-2"
        >
          <span>+</span>
          <span>Sorgu Ekle</span>
        </button>
      </div>

      {/* Stats Cards */}
      {stats && (
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          <div className="bg-white p-4 rounded-lg border">
            <div className="text-2xl font-bold text-blue-600">{stats.canonical_count}</div>
            <div className="text-sm text-gray-500">Referans Sorgu</div>
          </div>
          <div className="bg-white p-4 rounded-lg border">
            <div className="text-2xl font-bold text-green-600">{stats.custom_count}</div>
            <div className="text-sm text-gray-500">Özel Sorgu</div>
          </div>
          <div className="bg-white p-4 rounded-lg border">
            <div className="text-2xl font-bold text-purple-600">{stats.default_categories_count}</div>
            <div className="text-sm text-gray-500">Referans Kategorisi</div>
          </div>
          <div className="bg-white p-4 rounded-lg border">
            <div className="text-2xl font-bold text-orange-600">{stats.custom_categories_count}</div>
            <div className="text-sm text-gray-500">Özel Kategori</div>
          </div>
        </div>
      )}

      {/* Filters */}
      <div className="bg-white p-4 rounded-lg border space-y-4">
        <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
          {/* Search */}
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Ara</label>
            <input
              type="text"
              value={filters.search}
              onChange={(e) => setFilters(f => ({ ...f, search: e.target.value }))}
              placeholder="Sorgu ara..."
              className="w-full px-3 py-2 border rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
            />
          </div>
          
          {/* Category */}
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Kategori</label>
            <select
              value={filters.categoryId}
              onChange={(e) => setFilters(f => ({ ...f, categoryId: e.target.value }))}
              className="w-full px-3 py-2 border rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
            >
              <option value="">Tümü</option>
              {data?.categories.map(cat => (
                <option key={cat.id} value={cat.id}>
                  {cat.icon} {cat.name}
                </option>
              ))}
            </select>
          </div>
          
          {/* Source */}
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Kaynak</label>
            <select
              value={filters.sourceFilter}
              onChange={(e) => setFilters(f => ({ ...f, sourceFilter: e.target.value as any }))}
              className="w-full px-3 py-2 border rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
            >
              <option value="all">Tümü</option>
              <option value="canonical">Referans</option>
              <option value="custom">Özel</option>
            </select>
          </div>
          
          {/* Show Inactive */}
          <div className="flex items-end">
            <label className="flex items-center gap-2 cursor-pointer">
              <input
                type="checkbox"
                checked={filters.showInactive}
                onChange={(e) => setFilters(f => ({ ...f, showInactive: e.target.checked }))}
                className="w-4 h-4 rounded border-gray-300 text-blue-600 focus:ring-blue-500"
              />
              <span className="text-sm text-gray-700">Pasif sorguları göster</span>
            </label>
          </div>
        </div>
        
        <div className="text-sm text-gray-500">
          {filteredQueries.length} sorgu gösteriliyor
        </div>
      </div>

      {/* Add Query Form */}
      {showAddForm && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
          <div className="bg-white rounded-lg p-6 w-full max-w-lg mx-4">
            <h2 className="text-xl font-bold mb-4">Yeni Sorgu Ekle</h2>
            
            <form onSubmit={handleAddQuery} className="space-y-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Sorgu Metni *
                </label>
                <textarea
                  value={newQuery.text}
                  onChange={(e) => setNewQuery(q => ({ ...q, text: e.target.value }))}
                  placeholder="Örn: Son 6 ayda en çok değişen parçalar hangileri?"
                  rows={3}
                  className="w-full px-3 py-2 border rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
                  required
                />
              </div>
              
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Kategori
                </label>
                <select
                  value={newQuery.category_id}
                  onChange={(e) => setNewQuery(q => ({ ...q, category_id: e.target.value }))}
                  className="w-full px-3 py-2 border rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
                >
                  {data?.categories.map(cat => (
                    <option key={cat.id} value={cat.id}>
                      {cat.icon} {cat.name}
                    </option>
                  ))}
                </select>
              </div>
              
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Açıklama
                </label>
                <input
                  type="text"
                  value={newQuery.description}
                  onChange={(e) => setNewQuery(q => ({ ...q, description: e.target.value }))}
                  placeholder="Kısa açıklama..."
                  className="w-full px-3 py-2 border rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
                />
              </div>
              
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Etiketler
                </label>
                <input
                  type="text"
                  value={newQuery.tags}
                  onChange={(e) => setNewQuery(q => ({ ...q, tags: e.target.value }))}
                  placeholder="virgülle ayırın: malzeme, trend, analiz"
                  className="w-full px-3 py-2 border rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
                />
              </div>
              
              <div className="flex justify-end gap-3 pt-4">
                <button
                  type="button"
                  onClick={() => setShowAddForm(false)}
                  className="px-4 py-2 border rounded-lg hover:bg-gray-50"
                >
                  İptal
                </button>
                <button
                  type="submit"
                  disabled={saving}
                  className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50"
                >
                  {saving ? 'Kaydediliyor...' : 'Kaydet'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Query List */}
      <div className="space-y-6">
        {Object.entries(groupedQueries).map(([categoryId, queries]) => (
          <div key={categoryId} className="bg-white rounded-lg border overflow-hidden">
            {/* Category Header */}
            <div className="bg-gray-50 px-4 py-3 border-b">
              <h3 className="font-medium text-gray-900">
                {getCategoryName(categoryId)}
                <span className="ml-2 text-sm text-gray-500">({queries.length})</span>
              </h3>
            </div>
            
            {/* Queries */}
            <div className="divide-y">
              {queries.map((query) => (
                <div
                  key={query.id}
                  className={`p-4 hover:bg-gray-50 ${!query.is_active ? 'opacity-50' : ''}`}
                >
                  <div className="flex items-start justify-between gap-4">
                    <div className="flex-1 min-w-0">
                      <p className="text-gray-900">{query.text}</p>
                      
                      {query.description && (
                        <p className="text-sm text-gray-500 mt-1">{query.description}</p>
                      )}
                      
                      <div className="flex items-center gap-2 mt-2">
                        {/* Source badge */}
                        <span className={`text-xs px-2 py-0.5 rounded ${
                          query.source === 'canonical' 
                            ? 'bg-blue-100 text-blue-700' 
                            : 'bg-green-100 text-green-700'
                        }`}>
                          {query.source === 'canonical' ? '📚 Referans' : '⭐ Özel'}
                        </span>
                        
                        {/* Tags */}
                        {query.tags.slice(0, 3).map((tag, i) => (
                          <span key={i} className="text-xs px-2 py-0.5 bg-gray-100 text-gray-600 rounded">
                            {tag}
                          </span>
                        ))}
                      </div>
                    </div>
                    
                    {/* Actions (only for custom queries) */}
                    {query.source === 'custom' && (
                      <div className="flex items-center gap-2">
                        <button
                          onClick={() => handleToggleQuery(query.id)}
                          className={`p-2 rounded hover:bg-gray-100 ${
                            query.is_active ? 'text-green-600' : 'text-gray-400'
                          }`}
                          title={query.is_active ? 'Pasif yap' : 'Aktif yap'}
                        >
                          {query.is_active ? '👁️' : '👁️‍🗨️'}
                        </button>
                        <button
                          onClick={() => handleDeleteQuery(query.id)}
                          className="p-2 rounded hover:bg-red-50 text-red-600"
                          title="Sil"
                        >
                          🗑️
                        </button>
                      </div>
                    )}
                  </div>
                </div>
              ))}
            </div>
          </div>
        ))}
        
        {filteredQueries.length === 0 && (
          <div className="text-center py-12 text-gray-500">
            Sorgu bulunamadı
          </div>
        )}
      </div>
    </div>
  );
}
