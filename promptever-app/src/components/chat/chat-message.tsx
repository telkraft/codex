'use client';

import { useState, useRef, useEffect } from 'react';
import { Message, useSettingsStore } from '@/lib/store';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { cn, formatNumber } from '@/lib/utils';
import { EmailSendButton } from '@/components/email-send-button';

import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import {
  User,
  Bot,
  BarChart3,
  Brain,
  Sparkles,
  Clock,
  Cpu,
  Bug,
  Maximize2,
  X,
  TrendingUp,
  AreaChart,
  UserCircle,
  Palette,
  Copy,
  Check,
  Cloud,
  Home,
  AlertCircle,
} from 'lucide-react';
import {
  BarChart,
  Bar,
  LineChart,
  Line,
  AreaChart as RechartsArea,
  Area,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  Legend,
  Cell,
} from 'recharts';

interface ChatMessageProps {
  message: Message;
}

interface TableData {
  title: string;
  description?: string;
  columns: string[];
  rows: Array<Record<string, any>>;
  meta?: Record<string, any>;
}

const intentConfig = {
  statistical: {
    label: 'İstatistiksel',
    icon: BarChart3,
    variant: 'statistical' as const,
  },
  semantic: {
    label: 'Semantik',
    icon: Brain,
    variant: 'semantic' as const,
  },
  hybrid: {
    label: 'Hibrit',
    icon: Sparkles,
    variant: 'hybrid' as const,
  },
  error: {
    label: 'Hata',
    icon: Bot,
    variant: 'error' as const,
  },
  // 🆕 general_chat için intent
  general_chat: {
    label: 'Genel Sohbet',
    icon: AlertCircle,
    variant: 'outline' as const,
  },
};

const COLORS = {
  BAKIM: '#3b82f6',
  ONARIM: '#f97316',
  DIGER: '#06b6d4',
  count: '#8b5cf6',
  sum_cost: '#10b981',
  quantity: '#ec4899',
  primary: 'hsl(var(--primary))',
};

type ChartType = 'bar' | 'line' | 'area' | 'stacked';

// 🆕 Provider Label Map - 6 Provider
const PROVIDER_LABELS: Record<string, { label: string; icon: typeof Home; color: string }> = {
  groq: { label: 'Groq', icon: Cloud, color: 'text-blue-600 dark:text-blue-400' },
  openrouter: { label: 'OpenRouter', icon: Cloud, color: 'text-purple-600 dark:text-purple-400' },
  google: { label: 'Google AI', icon: Cloud, color: 'text-sky-600 dark:text-sky-400' },
  cerebras: { label: 'Cerebras', icon: Cloud, color: 'text-orange-600 dark:text-orange-400' },
  mistral: { label: 'Mistral', icon: Cloud, color: 'text-indigo-600 dark:text-indigo-400' },
  local: { label: 'Local', icon: Home, color: 'text-green-600 dark:text-green-400' },
};

// 🔧 Rol ve Davranış Label Map
const ROLE_LABELS: Record<string, string> = {
  servis_analisti: 'Servis Analisti',
  filo_yoneticisi: 'Filo Yöneticisi',
  teknik_uzman: 'Teknik Uzman',
  musteri_temsilcisi: 'Müşteri Temsilcisi',
  tedarik_zinciri_uzmani: 'Tedarik Zinciri Uzmanı',
  egitmen: 'Eğitmen',
  cto: 'CTO',
};

const BEHAVIOR_LABELS: Record<string, string> = {
  balanced: 'Analitik Yaklaşım',
  commentary: 'Yorumlayan',
  predictive: 'Hipotez Üreten',
  report: 'Rapor Oluşturan',
};

// Markdown tablosunu düzelt - tek satırdaki tabloları çok satırlı yap
function simpleFixMarkdownTable(text: string): string {
  if (!text || !text.includes('|')) return text;

  // |---|---| pattern'ini bul ve öncesini/sonrasını ayır
  const tablePattern = /(\|[^|]+(?:\|[^|]+)*)\s*(\|[-:]+(?:\|[-:]+)*\|)\s*(.+)/g;

  return text.replace(tablePattern, (match, header, separator, data) => {
    // Kolon sayısını bul
    const colCount = (separator.match(/---/g) || []).length;

    // Header'ı düzenle
    let headerLine = header.trim();
    if (!headerLine.startsWith('|')) headerLine = '|' + headerLine;
    if (!headerLine.endsWith('|')) headerLine = headerLine + '|';

    // Veri satırlarını parse et
    const values = data
      .split('|')
      .map((v: string) => v.trim())
      .filter((v: string) => v);

    const rows: string[] = [];

    for (let i = 0; i < values.length; i += colCount) {
      const rowValues = values.slice(i, i + colCount);
      if (rowValues.length === colCount) {
        rows.push('| ' + rowValues.join(' | ') + ' |');
      }
    }

    return headerLine + '\n' + separator + '\n' + rows.join('\n');
  });
}

// ============================================================================
// 🔧 FIX: Scroll helper - container içinde scroll yap, parent'ı etkileme
// ============================================================================
function scrollRowIntoViewWithinContainer(
  containerEl: HTMLElement | null,
  rowEl: HTMLElement | null
) {
  if (!containerEl || !rowEl) return;

  const containerRect = containerEl.getBoundingClientRect();
  const rowRect = rowEl.getBoundingClientRect();

  // Sticky header yüksekliği (thead sticky top-0)
  const theadEl = containerEl.querySelector('thead') as HTMLElement | null;
  const headerH = theadEl ? theadEl.getBoundingClientRect().height : 0;

  const padding = 10; // satırın tam görünmesi için küçük pay

  // Row'un container'a göre pozisyonu (scrollTop dahil)
  const rowTopRelative = rowRect.top - containerRect.top + containerEl.scrollTop;
  const rowBottomRelative = rowTopRelative + rowRect.height;

  // Görünür alan: sticky header'ı "kapalı alan" say
  const visibleTop = containerEl.scrollTop + headerH;
  const visibleBottom = containerEl.scrollTop + containerEl.clientHeight;

  // Row üstte gizli (ya da sticky header altında kalıyor)
  if (rowTopRelative < visibleTop + padding) {
    const target = Math.max(0, rowTopRelative - headerH - padding);
    containerEl.scrollTo({ top: target, behavior: 'smooth' });
    return;
  }

  // Row altta gizli
  if (rowBottomRelative > visibleBottom - padding) {
    const target = Math.max(0, rowBottomRelative - containerEl.clientHeight + padding);
    containerEl.scrollTo({ top: target, behavior: 'smooth' });
    return;
  }

  // Zaten tam görünürse scroll yapma
}

function CopyJsonButton({ text }: { text: string }) {
  const [copied, setCopied] = useState(false);

  const doCopy = async () => {
    try {
      await navigator.clipboard.writeText(text);
      setCopied(true);
      window.setTimeout(() => setCopied(false), 1200);
    } catch {
      // Clipboard izin/veri bloklanırsa sessizce geç (UI patlamasın)
    }
  };

  return (
    <Button
      variant="ghost"
      size="sm"
      className="h-7 px-2 text-xs"
      onClick={doCopy}
      title="Kopyala"
    >
      {copied ? (
        <>
          <Check className="h-3.5 w-3.5 mr-1" />
          Kopyalandı
        </>
      ) : (
        <>
          <Copy className="h-3.5 w-3.5 mr-1" />
          Kopyala
        </>
      )}
    </Button>
  );
}

// 🔧 Content'ten Normalize satırını ayır
function parseContent(content: string): { displayContent: string; normalizeInfo: string | null } {
  if (!content) return { displayContent: '', normalizeInfo: null };
  
  // "Normalize:" ile başlayan satırı bul
  const lines = content.split('\n');
  const normalizeLineIndex = lines.findIndex(line => 
    line.trim().toLowerCase().startsWith('normalize:')
  );
  
  if (normalizeLineIndex !== -1) {
    const normalizeLine = lines[normalizeLineIndex];
    const remainingLines = lines.filter((_, idx) => idx !== normalizeLineIndex);
    return {
      displayContent: remainingLines.join('\n').trim(),
      normalizeInfo: normalizeLine.trim()
    };
  }
  
  return { displayContent: content, normalizeInfo: null };
}

export function ChatMessage({ message }: ChatMessageProps) {
  const isUser = message.role === 'user';
  const intent = message.intent || 'statistical';
  const config = intentConfig[intent as keyof typeof intentConfig] || intentConfig.statistical;
  const { showDebug } = useSettingsStore();

  // 🆕 general_chat ve llm_enabled kontrolü
  const isGeneralChat = message.generalChat === true;
  const llmWasEnabled = message.llmUsed === true;
  const queryWasExecuted = message.queryExecuted !== false; // default true

  // 🆕 Provider bilgisi - sadece LLM kullanıldıysa göster
  const providerInfo = (message.provider && llmWasEnabled) ? PROVIDER_LABELS[message.provider] : null;
  const ProviderIcon = providerInfo?.icon || Cpu;

  // 🔧 Rol ve davranış label'larını al - sadece LLM kullanıldıysa
  const roleLabel = (message.llmRole && llmWasEnabled) ? ROLE_LABELS[message.llmRole] || message.llmRole : null;
  const behaviorLabel = (message.llmBehavior && llmWasEnabled) ? BEHAVIOR_LABELS[message.llmBehavior] || message.llmBehavior : null;

  // 🔧 Content'i parse et - Normalize satırını ayır
  const { displayContent, normalizeInfo } = parseContent(message.content);

  // 🆕 general_chat + LLM kapalı durumu için özel mesaj
  const showLLMDisabledWarning = isGeneralChat && !llmWasEnabled && !queryWasExecuted;

  // 🆕 Tablo/grafik gösterilmeli mi? (general_chat + query_executed:false ise hayır)
  const shouldShowDataVisualization = !isGeneralChat || queryWasExecuted;

  return (
    <div
      className={cn(
        'flex gap-3 message-enter',
        isUser ? 'flex-row-reverse' : 'flex-row'
      )}
    >
      <div
        className={cn(
          'flex h-8 w-8 shrink-0 items-center justify-center rounded-full',
          isUser ? 'bg-primary' : 'bg-muted'
        )}
      >
        {isUser ? (
          <User className="h-4 w-4 text-primary-foreground" />
        ) : (
          <Bot className="h-4 w-4 text-muted-foreground" />
        )}
      </div>

      <div
        className={cn(
          'flex max-w-[85%] flex-col gap-2',
          isUser ? 'items-end' : 'items-start'
        )}
      >
        {!isUser && message.intent && (
          <div className="flex items-center gap-2">
            <Badge variant={config.variant} className="gap-1">
              <config.icon className="h-3 w-3" />
              {config.label}
            </Badge>
            {message.scenario && (
              <Badge variant="outline" className="text-xs">
                {message.scenario}
              </Badge>
            )}
          </div>
        )}

        {/* 🔧 Normalize bilgisi - sadece debug modunda göster */}
        {showDebug && !isUser && normalizeInfo && (
          <div className="text-xs text-muted-foreground bg-muted/50 px-2 py-1 rounded border border-dashed">
            {normalizeInfo}
          </div>
        )}

        {/* 🆕 LLM Kapalı Uyarısı - general_chat + llm_enabled:false durumu */}
        {!isUser && showLLMDisabledWarning && (
          <Card className="w-full bg-amber-50 dark:bg-amber-950/30 border-amber-200 dark:border-amber-800">
            <CardContent className="p-3">
              <div className="flex items-center gap-2 text-amber-700 dark:text-amber-400">
                <AlertCircle className="h-4 w-4" />
                <p className="text-sm">
                  Dil modeli kapalı olduğu için genel sorulara cevap veremiyorum. 
                  Lütfen veri analizi ile ilgili bir soru sorun veya LLM'i etkinleştirin.
                </p>
              </div>
            </CardContent>
          </Card>
        )}

        {/* 🔧 Card sadece displayContent varsa ve LLM kapalı uyarısı yoksa göster */}
        {displayContent.trim() && !showLLMDisabledWarning && (
          <Card
            className={cn(
              isUser
                ? 'bg-primary text-primary-foreground'
                : 'bg-muted'
            )}
          >
            <CardContent className="p-3">
              <p className="text-sm whitespace-pre-wrap">{displayContent}</p>
            </CardContent>
          </Card>
        )}

        {/* Tables - 🆕 shouldShowDataVisualization kontrolü eklendi */}
        {!isUser && shouldShowDataVisualization && message.tables && message.tables.length > 0 && (
          <div className="w-full space-y-4">
            {message.tables.map((table: TableData, idx: number) => (
              <TableCard key={idx} table={table} scenario={message.scenario} />
            ))}
          </div>
        )}

        {!isUser && shouldShowDataVisualization && message.data && !message.tables && (
          <DataVisualization data={message.data} />
        )}

        {/* LLM Answer - sadece LLM kullanıldıysa göster */}
        {!isUser && llmWasEnabled && message.llmAnswer && (
          <Card className="w-full bg-gradient-to-br from-purple-50 to-blue-50 dark:from-purple-950 dark:to-blue-950 border-purple-200 dark:border-purple-800">
            <CardHeader className="pb-2">
              <CardTitle className="text-sm font-medium flex items-center gap-2">
                <Brain className="h-4 w-4 text-purple-600 dark:text-purple-400" />
                LLM Yorumu
                {/* 🆕 Provider Badge - LLM Yorumu başlığında */}
                {providerInfo && (
                  <Badge variant="outline" className={cn("text-xs gap-1 ml-auto", providerInfo.color)}>
                    <ProviderIcon className="h-3 w-3" />
                    {providerInfo.label}
                  </Badge>
                )}
              </CardTitle>
            </CardHeader>
            <CardContent>
              <div className="prose prose-sm dark:prose-invert max-w-none">
                <ReactMarkdown
                  remarkPlugins={[remarkGfm]}
                  components={{
                    h1: ({ node, ...props }: any) => <h1 className="text-lg font-bold mt-4 mb-2" {...props} />,
                    h2: ({ node, ...props }: any) => <h2 className="text-base font-bold mt-3 mb-2" {...props} />,
                    h3: ({ node, ...props }: any) => <h3 className="text-sm font-bold mt-2 mb-1" {...props} />,
                    p: ({ node, ...props }: any) => <p className="text-sm mb-2 leading-relaxed" {...props} />,
                    ul: ({ node, ...props }: any) => <ul className="text-sm list-disc list-inside mb-2 space-y-1" {...props} />,
                    ol: ({ node, ...props }: any) => <ol className="text-sm list-decimal list-inside mb-2 space-y-1" {...props} />,
                    li: ({ node, ...props }: any) => <li className="text-sm" {...props} />,
                    table: ({ node, ...props }: any) => (
                      <div className="overflow-x-auto my-3 rounded-lg border border-gray-200 dark:border-gray-700">
                        <table className="min-w-full text-xs divide-y divide-gray-200 dark:divide-gray-700" {...props} />
                      </div>
                    ),
                    thead: ({ node, ...props }: any) => (
                      <thead className="bg-gray-100 dark:bg-gray-800" {...props} />
                    ),
                    tbody: ({ node, ...props }: any) => (
                      <tbody className="divide-y divide-gray-200 dark:divide-gray-700 bg-white dark:bg-gray-900" {...props} />
                    ),
                    tr: ({ node, ...props }: any) => (
                      <tr className="hover:bg-gray-50 dark:hover:bg-gray-800" {...props} />
                    ),
                    th: ({ node, ...props }: any) => (
                      <th className="px-3 py-2 text-left font-semibold text-gray-700 dark:text-gray-300" {...props} />
                    ),
                    td: ({ node, ...props }: any) => (
                      <td className="px-3 py-2 text-gray-600 dark:text-gray-400" {...props} />
                    ),
                    code: ({ node, className, ...props }: any) => {
                      const isInline = !className?.includes('language-');
                      return isInline
                        ? <code className="bg-gray-200 dark:bg-gray-800 px-1 py-0.5 rounded text-xs" {...props} />
                        : <code className="block bg-gray-200 dark:bg-gray-800 p-2 rounded text-xs overflow-x-auto mb-2" {...props} />;
                    },
                    strong: ({ node, ...props }: any) => <strong className="font-semibold" {...props} />,
                    em: ({ node, ...props }: any) => <em className="italic" {...props} />,
                  }}
                >
                  {simpleFixMarkdownTable(message.llmAnswer)}
                </ReactMarkdown>
              </div>
            </CardContent>
          </Card>
        )}

        {/* Debug Panel */}
        {showDebug && !isUser && (message.data || message.tables) && (
          <Card className="w-full bg-yellow-50 dark:bg-yellow-900/20 border-yellow-300 dark:border-yellow-700">
            <CardHeader className="pb-2">
              <CardTitle className="text-sm font-medium flex items-center gap-2">
                <Bug className="h-4 w-4 text-yellow-600" />
                Debug (Meta / Plan)
              </CardTitle>
            </CardHeader>
            <CardContent>
              <div className="space-y-2">
                {message.intent && (
                  <p className="text-xs"><strong>Intent:</strong> {message.intent}</p>
                )}
                {message.scenario && (
                  <p className="text-xs"><strong>Scenario:</strong> {message.scenario}</p>
                )}
                {/* 🆕 general_chat ve query_executed bilgisi */}
                {message.generalChat !== undefined && (
                  <p className="text-xs"><strong>General Chat:</strong> {String(message.generalChat)}</p>
                )}
                {message.queryExecuted !== undefined && (
                  <p className="text-xs"><strong>Query Executed:</strong> {String(message.queryExecuted)}</p>
                )}
                {/* 🆕 Provider bilgisi debug panelinde - sadece LLM kullanıldıysa */}
                {llmWasEnabled && message.provider && (
                  <p className="text-xs"><strong>Provider:</strong> {message.provider}</p>
                )}
                {llmWasEnabled && message.llmRole && (
                  <p className="text-xs"><strong>LLM Role:</strong> {message.llmRole}</p>
                )}
                {llmWasEnabled && message.llmBehavior && (
                  <p className="text-xs"><strong>LLM Behavior:</strong> {message.llmBehavior}</p>
                )}

                {message.tables && message.tables.length > 0 && message.tables[0].meta && (
                  (() => {
                    const metaText = JSON.stringify(message.tables![0].meta, null, 2);
                    return (
                      <div className="space-y-1">
                        <div className="flex items-center justify-between">
                          <p className="text-xs font-medium">Meta:</p>
                          <CopyJsonButton text={metaText} />
                        </div>
                        <pre className="text-xs overflow-auto max-h-48 bg-muted p-2 rounded">
                          {metaText}
                        </pre>
                      </div>
                    );
                  })()
                )}

                {message.data && (
                  (() => {
                    const dataText = JSON.stringify(message.data, null, 2);
                    return (
                      <div className="space-y-1">
                        <div className="flex items-center justify-between">
                          <p className="text-xs font-medium">Data:</p>
                          <CopyJsonButton text={dataText} />
                        </div>
                        <pre className="text-xs overflow-auto max-h-48 bg-muted p-2 rounded">
                          {dataText}
                        </pre>
                      </div>
                    );
                  })()
                )}
              </div>
            </CardContent>
          </Card>
        )}

        {/* 📧 Email Gönder Butonu - shouldShowDataVisualization kontrolü */}
        {!isUser && shouldShowDataVisualization && (message.tables || message.data) && (
          <div className="flex items-center gap-2 pt-2">
            <EmailSendButton
              chatResponse={{
                intent: message.intent,
                scenario: message.scenario,
                tables: message.tables,
                answer: message.llmAnswer,
                statistics: message.data?.statistics,
                ...message.data,
              }}
              queryText={message.originalQuery || displayContent || 'Sorgu'}
            />
          </div>
        )}

        {/* 🔧 Footer - Provider, Model, Süre, Rol ve Davranış bilgisi - SADECE LLM KULLANILDIYSA */}
        {!isUser && llmWasEnabled && (message.model || message.elapsed || message.provider) && (
          <div className="flex flex-wrap items-center gap-3 text-xs text-muted-foreground">
            {/* 🆕 Provider Badge */}
            {message.provider && providerInfo && (
              <span className={cn("flex items-center gap-1 font-medium", providerInfo.color)}>
                <ProviderIcon className="h-3 w-3" />
                {providerInfo.label}
              </span>
            )}
            {/* Model */}
            {message.model && (
              <span className="flex items-center gap-1">
                <Cpu className="h-3 w-3" />
                {message.model}
              </span>
            )}
            {/* Süre */}
            {message.elapsed && (
              <span className="flex items-center gap-1">
                <Clock className="h-3 w-3" />
                {message.elapsed.toFixed(1)}s
              </span>
            )}
            {/* LLM kullanıldı mı */}
            {message.llmUsed && (
              <span className="flex items-center gap-1">
                <Brain className="h-3 w-3" />
                LLM
              </span>
            )}
            {/* Rol bilgisi */}
            {roleLabel && (
              <span className="flex items-center gap-1">
                <UserCircle className="h-3 w-3" />
                🎭 {roleLabel}
              </span>
            )}
            {/* Davranış bilgisi */}
            {behaviorLabel && (
              <span className="flex items-center gap-1">
                <Palette className="h-3 w-3" />
                ✨ {behaviorLabel}
              </span>
            )}
          </div>
        )}

        {/* 🆕 LLM Kapalıyken sadece süre göster */}
        {!isUser && !llmWasEnabled && message.elapsed && !showLLMDisabledWarning && (
          <div className="flex flex-wrap items-center gap-3 text-xs text-muted-foreground">
            <span className="flex items-center gap-1">
              <Clock className="h-3 w-3" />
              {message.elapsed.toFixed(1)}s
            </span>
          </div>
        )}
      </div>
    </div>
  );
}

// Kolon isimleri Türkçe mapping
const COLUMN_LABELS: Record<string, string> = {
  // Araç
  vehicleType: 'Araç Tipi',
  vehicleModel: 'Araç Modeli',
  vehicle: 'Araç',
  model: 'Araç Modeli',
  vehicleId: 'Araç ID',
  customerId: 'Müşteri',
  customer: 'Müşteri',
  serviceLocation: 'Servis Lokasyonu',

  // Malzeme
  materialName: 'Malzeme',
  materialFamily: 'Malzeme Ailesi',
  materialCode: 'Malzeme Kodu',
  material: 'Malzeme',

  // İşlem
  faultCode: 'Arıza Kodu',
  verbType: 'İşlem Tipi',

  // Zaman
  year: 'Yıl',
  month: 'Ay',
  season: 'Mevsim',
  date: 'Tarih',
  service: 'Servis',

  // Metrikler
  km: 'Km',
  quantity: 'Adet',
  cost: 'Maliyet',
  count: 'Adet',
  sum_cost: 'Toplam Maliyet',
  avg_cost: 'Ort. Maliyet',
  avg_km: 'Ort. Km',
  min_km: 'Min Km',
  max_km: 'Max Km',

  // Trend
  firstDate: 'İlk Tarih',
  lastDate: 'Son Tarih',
  firstPrice: 'İlk Fiyat',
  lastPrice: 'Son Fiyat',
  changeAbs: 'Fark',
  changePct: 'Değişim (%)',
  observations: 'Gözlem Sayısı',
  avgChangePct: 'Ort. Değişim (%)',
  materialsCount: 'Malzeme Sayısı',

  // Top / pivot
  entity: 'Varlık',
  entity_type: 'Varlık Tipi',

  // Next maintenance
  ratio: 'Oran (%)',
  rank: 'Sıra',

  // İşlem tipleri
  BAKIM: 'Bakım',
  ONARIM: 'Onarım',
  DIGER: 'Diğer',
};

// Kolon adını Türkçe'ye çevir
const getColumnLabel = (key: string): string => {
  return COLUMN_LABELS[key] || key;
};

function TableCard({ table, scenario }: { table: TableData; scenario?: string }) {
  const { showDebug } = useSettingsStore();

  const [chartType, setChartType] = useState<ChartType>('bar');
  const [showChart, setShowChart] = useState(true);
  const [expanded, setExpanded] = useState(false);
  const [selectedIndex, setSelectedIndex] = useState<number | null>(null);

  // Ana tablo ref'leri
  const tableRef = useRef<HTMLDivElement>(null);
  const rowRefs = useRef<(HTMLTableRowElement | null)[]>([]);

  // Modal tablo ref'leri
  const modalTableRef = useRef<HTMLDivElement>(null);
  const modalRowRefs = useRef<(HTMLTableRowElement | null)[]>([]);

  // ✅ FIX: Modal aç/kapa sırasında seçili satırı görünür yap
  // scrollIntoView yerine manuel container scroll kullan
  useEffect(() => {
    if (selectedIndex == null) return;

    const scrollSelectedIntoView = () => {
      const refs = expanded ? modalRowRefs : rowRefs;
      const containerRef = expanded ? modalTableRef : tableRef;
      const rowEl = refs.current[selectedIndex];
      const containerEl = containerRef.current;

      // 🔧 FIX: scrollIntoView yerine container-relative scroll
      scrollRowIntoViewWithinContainer(containerEl, rowEl);
    };

    // Modal açıldığında biraz bekle (render)
    const timer = setTimeout(scrollSelectedIntoView, 100);
    return () => clearTimeout(timer);
  }, [expanded, selectedIndex]);

  // Sayısal kolonları belirle
  const valueColumns = table.columns.filter((col) =>
    table.rows.some((row) => typeof row[col] === 'number')
  );

  // Label kolonu (ilk non-numeric)
  const labelColumn = table.columns.find(
    (col) => !valueColumns.includes(col)
  ) || table.columns[0];

  // Grafik verisi hazırla
  const chartData = table.rows.map((row, idx) => {
    const entry: Record<string, any> = {
      name: String(row[labelColumn] || `#${idx + 1}`),
      _index: idx,
    };
    valueColumns.forEach((col) => {
      entry[col] = row[col];
    });
    return entry;
  });

  // Chart yüksekliği
  const chartHeight = Math.min(300, Math.max(200, table.rows.length * 30));

  // Satır seçimi handler
  const handleRowClick = (index: number) => {
    setSelectedIndex(selectedIndex === index ? null : index);
  };

  // 🔧 FIX: Chart'ta tıklama - container-relative scroll kullan
  const handleChartClick = (data: any, isModal: boolean = false) => {
    if (data && data.activePayload && data.activePayload[0]) {
      const clickedIndex = data.activePayload[0].payload._index;
      handleRowClick(clickedIndex);

      // Tabloda ilgili satıra scroll - container içinde
      const refs = isModal ? modalRowRefs : rowRefs;
      const containerRef = isModal ? modalTableRef : tableRef;
      const rowEl = refs.current[clickedIndex];
      const containerEl = containerRef.current;

      // 🔧 FIX: scrollIntoView yerine container-relative scroll
      scrollRowIntoViewWithinContainer(containerEl, rowEl);
    }
  };

  // ============================================================================
  // 🔧 FIX: Legend'ı grafiğin üstüne taşı - verticalAlign="top" ve wrapperStyle
  // ============================================================================
  const renderLegend = () => (
    <Legend 
      verticalAlign="top" 
      height={36}
      wrapperStyle={{ 
        paddingBottom: '10px',
        fontSize: '12px'
      }}
    />
  );

  // 🔧 FIX: Veri sayısına göre X ekseni interval hesapla
  const calculateXAxisInterval = (dataLength: number): number | 'preserveStartEnd' => {
    if (dataLength <= 10) return 0;
    if (dataLength <= 20) return 1;
    if (dataLength <= 40) return 2;
    if (dataLength <= 80) return 4;
    if (dataLength <= 150) return Math.floor(dataLength / 20);
    return Math.floor(dataLength / 15);
  };

  // 🔧 FIX: Uzun etiketleri kısalt
  const formatXAxisLabel = (value: string): string => {
    if (!value) return '';
    if (value.length > 12) return value.substring(0, 10) + '..';
    return value;
  };

  const xAxisInterval = calculateXAxisInterval(chartData.length);

  // Chart render
  const renderChart = (isModal: boolean = false) => {
    if (chartType === 'line') {
      return (
        <LineChart data={chartData} onClick={(e) => handleChartClick(e, isModal)}>
          <CartesianGrid strokeDasharray="3 3" opacity={0.3} />
          <XAxis
            dataKey="name"
            tick={{ fontSize: 10 }}
            angle={-45}
            textAnchor="end"
            height={70}
            interval={xAxisInterval}
            tickFormatter={formatXAxisLabel}
          />
          <YAxis tick={{ fontSize: 11 }} />
          <Tooltip />
          {renderLegend()}
          {valueColumns.map((field, i) => (
            <Line
              key={field}
              type="monotone"
              dataKey={field}
              name={getColumnLabel(field)}
              stroke={COLORS[field as keyof typeof COLORS] || `hsl(${i * 60}, 70%, 50%)`}
              strokeWidth={2}
              dot={{ r: 4 }}
              activeDot={{ r: 6 }}
            />
          ))}
        </LineChart>
      );
    }

    if (chartType === 'area') {
      return (
        <RechartsArea data={chartData} onClick={(e) => handleChartClick(e, isModal)}>
          <CartesianGrid strokeDasharray="3 3" opacity={0.3} />
          <XAxis
            dataKey="name"
            tick={{ fontSize: 10 }}
            angle={-45}
            textAnchor="end"
            height={70}
            interval={xAxisInterval}
            tickFormatter={formatXAxisLabel}
          />
          <YAxis tick={{ fontSize: 11 }} />
          <Tooltip />
          {renderLegend()}
          {valueColumns.map((field, i) => (
            <Area
              key={field}
              type="monotone"
              dataKey={field}
              name={getColumnLabel(field)}
              stroke={COLORS[field as keyof typeof COLORS] || `hsl(${i * 60}, 70%, 50%)`}
              fill={COLORS[field as keyof typeof COLORS] || `hsl(${i * 60}, 70%, 50%)`}
              fillOpacity={0.3}
            />
          ))}
        </RechartsArea>
      );
    }

    // Bar veya Stacked
    return (
      <BarChart data={chartData} onClick={(e) => handleChartClick(e, isModal)}>
        <CartesianGrid strokeDasharray="3 3" opacity={0.3} />
        <XAxis
          dataKey="name"
          tick={{ fontSize: 10 }}
          angle={-45}
          textAnchor="end"
          height={70}
          interval={xAxisInterval}
          tickFormatter={formatXAxisLabel}
        />
        <YAxis tick={{ fontSize: 11 }} />
        <Tooltip />
        {renderLegend()}
        {valueColumns.map((field, i) => (
          <Bar
            key={field}
            dataKey={field}
            name={getColumnLabel(field)}
            stackId={chartType === 'stacked' ? 'stack' : undefined}
            fill={COLORS[field as keyof typeof COLORS] || `hsl(${i * 60}, 70%, 50%)`}
          >
            {chartData.map((entry, index) => (
              <Cell
                key={`cell-${index}`}
                fill={selectedIndex === index ? '#f97316' : COLORS[field as keyof typeof COLORS] || `hsl(${i * 60}, 70%, 50%)`}
                stroke={selectedIndex === index ? '#fff' : 'none'}
                strokeWidth={selectedIndex === index ? 2 : 0}
                cursor="pointer"
              />
            ))}
          </Bar>
        ))}
      </BarChart>
    );
  };

  // Tablo render - isModal parametresi ile
  // 🔧 FIX: Tablo render - overscroll-contain eklendi
  const renderTable = (isModal: boolean = false) => {
    const refs = isModal ? modalRowRefs : rowRefs;
    const containerRef = isModal ? modalTableRef : tableRef;
    const maxHeight = isModal ? 'max-h-72' : 'max-h-80';
    const textSize = isModal ? 'text-sm' : 'text-xs';

    return (
      <div 
        ref={containerRef} 
        className={`rounded border ${maxHeight} overflow-auto overscroll-contain`}
        // 🔧 FIX: Scroll chaining'i durdur
        style={{ overscrollBehavior: 'contain' }}
      >
        <table className={`w-full ${textSize}`}>
          <thead className="bg-muted sticky top-0 z-10">
            <tr>
              <th className="px-2 py-2 text-left font-medium border-b w-10">#</th>
              {table.columns.map((col) => (
                <th key={col} className="px-3 py-2 text-left font-medium border-b">
                  {getColumnLabel(col)}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {table.rows.map((row, idx) => (
              <tr
                key={idx}
                ref={(el) => { refs.current[idx] = el; }}
                className={cn(
                  "border-b cursor-pointer transition-colors",
                  selectedIndex === idx
                    ? "bg-orange-100 dark:bg-orange-900/30 hover:bg-orange-200 dark:hover:bg-orange-900/50"
                    : "hover:bg-muted/50"
                )}
                onClick={() => handleRowClick(idx)}
              >
                <td className="px-2 py-2 text-muted-foreground font-medium">{idx + 1}</td>
                {table.columns.map((col) => (
                  <td key={col} className="px-3 py-2">
                    {typeof row[col] === 'number'
                      ? formatNumber(row[col])
                      : String(row[col] ?? '-')}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    );
  };

  // ✅ Debug-only "Normalize: ... | Intent: ... | Shape: ..." satırını yakala
  const isDebugLine = (() => {
    const d = (table.description || '').trim().toLowerCase();
    if (!d) return false;
    return (
      d.startsWith('normalize:') ||
      d.includes('| intent:') ||
      d.includes('| shape:') ||
      d.includes('intent:') && d.includes('shape:')
    );
  })();

  const shouldShowDescription = !!table.description && (!isDebugLine || showDebug);

  return (
    <>
      <Card className="w-full">
        <CardHeader className="pb-2">
          <div className="flex items-center justify-between">
            <div>
              <CardTitle className="text-sm font-medium flex items-center gap-2">
                <BarChart3 className="h-4 w-4" />
                {table.title}
              </CardTitle>

              {/* ✅ Normalize satırı sadece Debug açıkken görünür */}
              {shouldShowDescription && (
                <p className="text-xs text-muted-foreground mt-1">{table.description}</p>
              )}
            </div>
            <div className="flex items-center gap-1">
              <Button
                variant={showChart ? 'default' : 'outline'}
                size="sm"
                className="h-7 text-xs"
                onClick={() => setShowChart(!showChart)}
              >
                Grafik
              </Button>
              {showChart && (
                <Button
                  variant="outline"
                  size="sm"
                  className="h-7 w-7 p-0"
                  onClick={() => setExpanded(true)}
                >
                  <Maximize2 className="h-3 w-3" />
                </Button>
              )}
            </div>
          </div>

          {showChart && (
            <div className="flex items-center gap-2 mt-2 flex-wrap">
              {[
                { type: 'bar' as ChartType, icon: BarChart3, label: 'Çubuk' },
                { type: 'stacked' as ChartType, icon: BarChart3, label: 'Yığın' },
                { type: 'line' as ChartType, icon: TrendingUp, label: 'Çizgi' },
                { type: 'area' as ChartType, icon: AreaChart, label: 'Alan' },
              ].map(({ type, icon: Icon, label }) => (
                <Button
                  key={type}
                  variant={chartType === type ? 'default' : 'ghost'}
                  size="sm"
                  className="h-6 text-xs px-2"
                  onClick={() => setChartType(type)}
                >
                  <Icon className="h-3 w-3 mr-1" />
                  {label}
                </Button>
              ))}
              {selectedIndex !== null && (
                <Button
                  variant="ghost"
                  size="sm"
                  className="h-6 text-xs px-2 ml-auto"
                  onClick={() => setSelectedIndex(null)}
                >
                  <X className="h-3 w-3 mr-1" />
                  Temizle
                </Button>
              )}
            </div>
          )}
        </CardHeader>

        <CardContent className="space-y-4">
          {showChart && chartData.length >= 2 && (
            <ResponsiveContainer width="100%" height={chartHeight}>
              {renderChart(false)}
            </ResponsiveContainer>
          )}

          {renderTable(false)}

          <p className="text-xs text-muted-foreground text-center">
            Toplam {table.rows.length} kayıt
            {selectedIndex !== null && ` • Seçili: #${selectedIndex + 1}`}
          </p>
        </CardContent>
      </Card>

      {/* Modal - Genişletilmiş Görünüm */}
      {expanded && (
        <div
          className="fixed inset-0 bg-black/70 flex items-center justify-center z-50 p-4"
          onClick={(e) => {
            if (e.target === e.currentTarget) setExpanded(false);
          }}
        >
          <Card className="w-full max-w-7xl max-h-[95vh] overflow-hidden">
            <CardHeader className="flex flex-row items-center justify-between pb-2 border-b">
              <div>
                <CardTitle className="text-lg">{table.title}</CardTitle>
                {/* modal içinde description: debug kuralı aynı */}
                {shouldShowDescription && (
                  <p className="text-sm text-muted-foreground">{table.description}</p>
                )}
              </div>
              <div className="flex items-center gap-2">
                {[
                  { type: 'bar' as ChartType, icon: BarChart3, label: 'Çubuk' },
                  { type: 'stacked' as ChartType, icon: BarChart3, label: 'Yığın' },
                  { type: 'line' as ChartType, icon: TrendingUp, label: 'Çizgi' },
                  { type: 'area' as ChartType, icon: AreaChart, label: 'Alan' },
                ].map(({ type, icon: Icon, label }) => (
                  <Button
                    key={type}
                    variant={chartType === type ? 'default' : 'outline'}
                    size="sm"
                    onClick={() => setChartType(type)}
                  >
                    <Icon className="h-4 w-4 mr-1" />
                    {label}
                  </Button>
                ))}
                {selectedIndex !== null && (
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() => setSelectedIndex(null)}
                  >
                    <X className="h-4 w-4 mr-1" />
                    Temizle
                  </Button>
                )}
                <Button variant="ghost" size="icon" onClick={() => setExpanded(false)}>
                  <X className="h-5 w-5" />
                </Button>
              </div>
            </CardHeader>
            <CardContent className="p-4 overflow-auto" style={{ maxHeight: 'calc(95vh - 80px)' }}>
              {/* Modal içi grafik */}
              <div className="mb-4">
                <ResponsiveContainer width="100%" height={400}>
                  {renderChart(true)}
                </ResponsiveContainer>
              </div>

              {/* Modal içi tablo */}
              {renderTable(true)}

              <p className="text-sm text-muted-foreground text-center mt-3">
                Toplam {table.rows.length} kayıt
                {selectedIndex !== null && ` • Seçili: #${selectedIndex + 1}`}
              </p>
            </CardContent>
          </Card>
        </div>
      )}
    </>
  );
}

function DataVisualization({ data }: { data: Record<string, unknown> }) {
  return null;
}
