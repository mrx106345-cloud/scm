import { Suspense, lazy } from 'react';
import { BrowserRouter as Router, Routes, Route, Link, useParams } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { ChatPanel } from './explainChat';
import { SupplierList } from './features/suppliers/SupplierList';
import { SupplierDetail } from './features/suppliers/SupplierDetail';
import { ItemDetail } from './features/items/ItemPage';
import { ErrorBoundary } from './components/error-boundary';

// Create a client instance for use across the app
const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      retry: 1,
      refetchOnWindowFocus: false,
    },
  },
});

function SupplierPageRouter() {
  const { id } = useParams<{ id: string }>();
  return id ? <SupplierDetail supplierId={id} /> : <SupplierList />;
}

function ItemPageRouter() {
  const { id } = useParams<{ id: string }>();
  return id ? <ItemDetail itemId={id} /> : <div>Item not found</div>;
}

// Lazy-loaded dashboard (route-level code splitting)
const Dashboard = lazy(() =>
  import('@/features/dashboard/Dashboard').then((m) => ({ default: m.Dashboard })),
);

const LoadingFallback = () => (
  <div className="flex items-center justify-center h-full">
    <div className="h-8 w-8 animate-spin rounded-full border-2 border-primary border-t-transparent" />
  </div>
);

/** App shell: dashboard plus the docked chat panel (Part M item 9). */
export function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <ErrorBoundary>
        <Router>
          <div style={{ display: 'flex', gap: '1rem', padding: '1rem' }}>
            <nav
              aria-label="Primary"
              style={{
                flex: 0,
                width: '220px',
                borderRight: '1px solid #ccc',
                paddingRight: '1rem',
              }}
            >
              <ul style={{ listStyle: 'none', padding: 0 }}>
                <li>
                  <Link to="/">Dashboard</Link>
                </li>
                <li>
                  <Link to="/suppliers">Suppliers</Link>
                </li>
              </ul>
            </nav>
            <div style={{ flex: 1 }}>
              <Suspense fallback={<LoadingFallback />}>
                <Routes>
                  <Route
                    path="/"
                    element={
                      <ErrorBoundary>
                        <Dashboard />
                      </ErrorBoundary>
                    }
                  />
                  <Route
                    path="/suppliers"
                    element={
                      <ErrorBoundary>
                        <SupplierPageRouter />
                      </ErrorBoundary>
                    }
                  />
                  <Route
                    path="/suppliers/:id"
                    element={
                      <ErrorBoundary>
                        <SupplierPageRouter />
                      </ErrorBoundary>
                    }
                  />
                  <Route
                    path="/items/:id"
                    element={
                      <ErrorBoundary>
                        <ItemPageRouter />
                      </ErrorBoundary>
                    }
                  />
                </Routes>
              </Suspense>
            </div>
            <div style={{ flex: 0, width: '300px' }}>
              <ErrorBoundary>
                <ChatPanel />
              </ErrorBoundary>
            </div>
          </div>
        </Router>
      </ErrorBoundary>
    </QueryClientProvider>
  );
}
