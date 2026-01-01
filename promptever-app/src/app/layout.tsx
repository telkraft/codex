import type { Metadata } from 'next';
import { Inter } from 'next/font/google';
import './globals.css';
import { Providers } from '@/components/providers';
import { Sidebar } from '@/components/layout/sidebar';
import { Header } from '@/components/layout/header';

const inter = Inter({ subsets: ['latin'] });

export const metadata: Metadata = {
  title: 'Promptever | Enterprise Experience Analytics',
  description: 'Kurumsal Deneyim Mimarisi - xAPI + JSON-LD ile Dijital Egemenlik',
  icons: {
    icon: '/favicon.ico',
  },
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="tr" suppressHydrationWarning>
      <body className={inter.className}>
        <Providers>
          <div className="flex h-screen overflow-hidden bg-background">
            {/* Sidebar */}
            <Sidebar />
            
            {/* Main content area */}
            <div className="flex flex-1 flex-col overflow-hidden">
              {/* Header */}
              <Header />
              
              {/* Page content */}
              <main className="flex-1 overflow-auto">
                {children}
              </main>
            </div>
          </div>
        </Providers>
      </body>
    </html>
  );
}
