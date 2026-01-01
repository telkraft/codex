import QuickQueriesManager from '@/components/quick-queries-manager';

export const metadata = {
  title: 'Referans Sorgular | Promptever',
  description: 'Referans sorgu yönetimi',
};

export default function QuickQueriesPage() {
  return (
    <div className="container mx-auto py-8 px-4">
      <QuickQueriesManager />
    </div>
  );
}
