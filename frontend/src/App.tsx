import { Suspense, lazy } from 'react';
import {
  BrowserRouter as Router,
  Routes,
  Route,
  useParams,
  useNavigate,
  Link,
} from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { ChatPanel } from './explainChat';
import { SupplierList } from './features/suppliers/SupplierList';
import { SupplierDetail } from './features/suppliers/SupplierDetail';
import { ItemDetail } from './features/items/ItemPage';
import { LoginPage } from './features/auth';
import { ErrorBoundary } from './components/error-boundary';
import { ProtectedRoute } from './components/layout/ProtectedRoute';
import { AuthProvider, useAuth } from './hooks/useAuth';
import { toast } from 'react-hot-toast';

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

function NavBar() {
  const { user, isAuthenticated, logout } = useAuth();
  const navigate = useNavigate();

  const handleLogout = async () => {
    try {
      await logout(); // useAuth clears local state even if the server call fails
      toast.success('Logged out');
    } catch {
      // Server unreachable etc.: still sign out locally and go to /login.
      toast.error('Logout failed; signed out locally');
    }
    navigate('/login', { replace: true });
  };

  if (!isAuthenticated) return null;

  const linkCls =
    'w-full text-left px-3 py-2 text-sm text-muted-foreground hover:bg-accent rounded transition-colors';

  return (
    <div
      className="flex flex-col gap-2 pt-4 border-l border-border px-3"
      style={{ flex: 0, width: '210px' }}
    >
      <div className="text-xs font-semibold text-muted-foreground uppercase mb-2">
        {user?.username} ({user?.role})
      </div>
      <nav aria-label="Primary" className="flex flex-col gap-1">
        <Link to="/" className={linkCls}>
          Dashboard
        </Link>
        <Link to="/suppliers" className={linkCls}>
          Suppliers
        </Link>
        <button onClick={handleLogout} className={linkCls}>
          Sign out
        </button>
      </nav>
    </div>
  );
}

/** App shell: dashboard plus the docked chat panel (Part M item 9). */
export function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <AuthProvider>
        <ErrorBoundary>
          <Router>
            <div style={{ display: 'flex', gap: '1rem', padding: '1rem' }}>
              <NavBar />
              <div style={{ flex: 1 }}>
                <Suspense fallback={<LoadingFallback />}>
                  <Routes>
                    <Route
                      path="/login"
                      element={
                        <ErrorBoundary>
                          <LoginPage />
                        </ErrorBoundary>
                      }
                    />
                    <Route
                      path="/"
                      element={
                        <ProtectedRoute>
                          <ErrorBoundary>
                            <Dashboard />
                          </ErrorBoundary>
                        </ProtectedRoute>
                      }
                    />
                    <Route
                      path="/suppliers"
                      element={
                        <ProtectedRoute>
                          <ErrorBoundary>
                            <SupplierPageRouter />
                          </ErrorBoundary>
                        </ProtectedRoute>
                      }
                    />
                    <Route
                      path="/suppliers/:id"
                      element={
                        <ProtectedRoute>
                          <ErrorBoundary>
                            <SupplierPageRouter />
                          </ErrorBoundary>
                        </ProtectedRoute>
                      }
                    />
                    <Route
                      path="/items/:id"
                      element={
                        <ProtectedRoute>
                          <ErrorBoundary>
                            <ItemPageRouter />
                          </ErrorBoundary>
                        </ProtectedRoute>
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
      </AuthProvider>
    </QueryClientProvider>
  );
}
