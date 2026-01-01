'use client';

import { Suspense } from 'react';
import { ChatInterface } from '@/components/chat/chat-interface';
import { Loader2 } from 'lucide-react';

function ChatLoading() {
  return (
    <div className="flex h-full items-center justify-center">
      <div className="text-center">
        <Loader2 className="h-8 w-8 animate-spin text-muted-foreground mx-auto mb-2" />
        <p className="text-sm text-muted-foreground">Yükleniyor...</p>
      </div>
    </div>
  );
}

export default function ChatPage() {
  return (
    <div className="flex h-full">
      <div className="flex-1">
        <Suspense fallback={<ChatLoading />}>
          <ChatInterface />
        </Suspense>
      </div>
    </div>
  );
}
