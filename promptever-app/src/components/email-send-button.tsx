'use client';

import React, { useState } from 'react';

// ============================================================================
// TYPES
// ============================================================================

interface ChatResponse {
  intent?: string;
  scenario?: string;
  tables?: Array<{
    title: string;
    description?: string;
    columns: string[];
    rows: Array<Record<string, any>>;
    meta?: Record<string, any>;
  }>;
  answer?: string;
  statistics?: Record<string, any>;
  llm?: {
    model: string;
    answer: string;
    latency_sec: number;
  };
  llmAnswer?: string;
  [key: string]: any;
}

interface EmailSendButtonProps {
  chatResponse: ChatResponse;
  queryText: string;
  className?: string;
  apiUrl?: string;
  llmUsed?: boolean;
}

// ============================================================================
// COMPONENT
// ============================================================================

export function EmailSendButton({
  chatResponse,
  queryText,
  className = '',
  apiUrl = process.env.NEXT_PUBLIC_RAG_API_URL || 'https://app.promptever.com/api/rag',
  llmUsed,
}: EmailSendButtonProps) {
  const [isOpen, setIsOpen] = useState(false);
  const [recipients, setRecipients] = useState('');
  const [subject, setSubject] = useState('');
  const [note, setNote] = useState('');
  const [includeLlmAnswer, setIncludeLlmAnswer] = useState(true);
  const [sending, setSending] = useState(false);
  const [result, setResult] = useState<{ success: boolean; message: string } | null>(null);

  // LLM yanıtı var mı kontrol et - daha geniş kontrol
  const llmAnswer = chatResponse?.answer || chatResponse?.llmAnswer || chatResponse?.llm?.answer;
  const hasLlmAnswer = Boolean(llmAnswer && llmAnswer.trim().length > 0);
  
  // llmUsed prop'u verilmişse onu kullan, yoksa hasLlmAnswer'a bak
  const showLlmCheckbox = llmUsed !== undefined ? (llmUsed && hasLlmAnswer) : hasLlmAnswer;

  const handleSend = async () => {
    const emailList = recipients
      .split(/[,\n]/)
      .map((e) => e.trim())
      .filter((e) => e.includes('@'));

    if (emailList.length === 0) {
      setResult({ success: false, message: 'Geçerli email adresi girin' });
      return;
    }

    setSending(true);
    setResult(null);

    try {
      const response = await fetch(`${apiUrl}/email/send`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          recipients: emailList,
          subject: subject || undefined,
          query_text: queryText,
          chat_response: chatResponse,
          include_tables: true,
          include_llm_answer: showLlmCheckbox ? includeLlmAnswer : false,
          include_statistics: true,
          user_note: note.trim() || undefined,
        }),
      });

      const data = await response.json();

      if (data.success) {
        setResult({
          success: true,
          message: `${data.sent_to?.length || 1} kişiye email gönderildi`,
        });
        setTimeout(() => {
          setIsOpen(false);
          setResult(null);
          setRecipients('');
          setSubject('');
          setNote('');
        }, 2000);
      } else {
        setResult({
          success: false,
          message: data.message || 'Email gönderilemedi',
        });
      }
    } catch (error) {
      console.error('Email gönderme hatası:', error);
      setResult({
        success: false,
        message: error instanceof Error ? error.message : 'Bağlantı hatası',
      });
    } finally {
      setSending(false);
    }
  };

  return (
    <>
      {/* Trigger Button */}
      <button
        onClick={() => setIsOpen(true)}
        className={`inline-flex items-center gap-2 px-3 py-1.5 text-sm font-medium 
          text-blue-600 bg-blue-50 hover:bg-blue-100 rounded-lg transition-colors
          border border-blue-200 hover:border-blue-300 ${className}`}
        title="Sonucu email olarak gönder"
      >
        <span>📧</span>
        <span>Email Gönder</span>
      </button>

      {/* Modal */}
      {isOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50">
          <div className="bg-white rounded-xl shadow-2xl w-full max-w-md mx-4 overflow-hidden">
            {/* Header */}
            <div className="px-6 py-4 border-b border-gray-100 bg-gray-50">
              <h3 className="text-lg font-semibold text-gray-800 flex items-center gap-2">
                <span>📧</span> Sonucu Email Gönder
              </h3>
            </div>

            {/* Content */}
            <div className="px-6 py-4 space-y-4">
              {/* Query Preview */}
              <div className="p-3 bg-gray-50 rounded-lg text-sm">
                <div className="text-gray-500 text-xs mb-1">Sorgu:</div>
                <div className="font-medium text-gray-800">{queryText}</div>
                <div className="flex flex-wrap gap-2 mt-2">
                  {chatResponse?.intent && (
                    <span className="px-2 py-0.5 bg-blue-100 text-blue-700 rounded text-xs">
                      {chatResponse.intent}
                    </span>
                  )}
                  {chatResponse?.scenario && (
                    <span className="px-2 py-0.5 bg-green-100 text-green-700 rounded text-xs">
                      {chatResponse.scenario}
                    </span>
                  )}
                </div>
              </div>

              {/* Recipients */}
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Alıcılar <span className="text-red-500">*</span>
                </label>
                <textarea
                  value={recipients}
                  onChange={(e) => setRecipients(e.target.value)}
                  placeholder="email@example.com&#10;Her satıra bir email veya virgülle ayırın"
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm
                    focus:ring-2 focus:ring-blue-500 focus:border-blue-500 resize-none"
                  rows={2}
                />
              </div>

              {/* Subject */}
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Konu <span className="text-gray-400 font-normal">(Opsiyonel)</span>
                </label>
                <input
                  type="text"
                  value={subject}
                  onChange={(e) => setSubject(e.target.value)}
                  placeholder="Boş bırakılırsa otomatik oluşturulur"
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm
                    focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
                />
              </div>

              {/* User Note */}
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Not / Açıklama <span className="text-gray-400 font-normal">(Opsiyonel)</span>
                </label>
                <textarea
                  value={note}
                  onChange={(e) => setNote(e.target.value)}
                  placeholder="Örn: Lütfen kırmızı ile işaretli değerlere dikkat edin..."
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm
                    focus:ring-2 focus:ring-blue-500 focus:border-blue-500 resize-none"
                  rows={2}
                />
              </div>

              {/* LLM Option - sadece LLM yanıtı varsa göster */}
              {showLlmCheckbox && (
                <div className="pt-2 border-t border-gray-100">
                  <label className="flex items-center gap-2 text-sm text-gray-600 cursor-pointer">
                    <input
                      type="checkbox"
                      checked={includeLlmAnswer}
                      onChange={(e) => setIncludeLlmAnswer(e.target.checked)}
                      className="w-4 h-4 rounded border-gray-300 text-blue-600 
                        focus:ring-blue-500"
                    />
                    LLM yorumunu dahil et
                  </label>
                </div>
              )}

              {/* Result Message */}
              {result && (
                <div
                  className={`p-3 rounded-lg text-sm flex items-center gap-2 ${
                    result.success
                      ? 'bg-green-50 text-green-700 border border-green-200'
                      : 'bg-red-50 text-red-700 border border-red-200'
                  }`}
                >
                  <span>{result.success ? '✅' : '❌'}</span>
                  {result.message}
                </div>
              )}
            </div>

            {/* Footer */}
            <div className="px-6 py-4 border-t border-gray-100 bg-gray-50 flex justify-end gap-3">
              <button
                onClick={() => {
                  setIsOpen(false);
                  setResult(null);
                }}
                className="px-4 py-2 text-sm font-medium text-gray-700 hover:bg-gray-200 
                  rounded-lg transition-colors"
              >
                İptal
              </button>
              <button
                onClick={handleSend}
                disabled={sending || !recipients.includes('@')}
                className="px-4 py-2 text-sm font-medium text-white bg-blue-600 
                  hover:bg-blue-700 rounded-lg transition-colors disabled:opacity-50 
                  disabled:cursor-not-allowed flex items-center gap-2"
              >
                {sending ? (
                  <>
                    <span className="animate-spin">⏳</span>
                    Gönderiliyor...
                  </>
                ) : (
                  <>
                    <span>📤</span>
                    Gönder
                  </>
                )}
              </button>
            </div>
          </div>
        </div>
      )}
    </>
  );
}

export default EmailSendButton;
