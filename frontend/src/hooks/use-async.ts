import { useState, useCallback } from 'react';

export interface UseAsyncState<T> {
  data: T | null;
  loading: boolean;
  error: string | null;
  refetch: () => Promise<void>;
}

export function useAsync<T>(
  initialData: T | null = null,
  initialLoading = false,
  initialError: string | null = null,
): UseAsyncState<T> {
  const [data, setData] = useState<T | null>(initialData);
  const [loading, setLoading] = useState<boolean>(initialLoading);
  const [error, setError] = useState<string | null>(initialError);

  const refetch = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const result = await new Promise<T>((resolve) => {
        // Default implementation - hooks using this should override with real fetch
        resolve(undefined as unknown as T);
      });
      setData(result);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'An error occurred');
    } finally {
      setLoading(false);
    }
  }, []);

  return { data, loading, error, refetch };
}

export function usePaginatedAsync<T>(
  initialData: T[] = [],
  initialLoading = false,
  initialError: string | null = null,
) {
  const [data, setData] = useState<T[]>(initialData);
  const [loading, setLoading] = useState<boolean>(initialLoading);
  const [error, setError] = useState<string | null>(initialError);
  const [page, setPage] = useState(1);
  const [pageSize] = useState(20);
  const [total, setTotal] = useState(0);

  const refetch = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const result = await new Promise<{
        results: T[];
        total: number;
        page: number;
        pageSize: number;
      }>((resolve) => resolve({ results: [], total: 0, page: 1, pageSize: 20 }));
      setData(result.results);
      setTotal(result.total);
      setPage(result.page);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'An error occurred');
    } finally {
      setLoading(false);
    }
  }, []);

  const loadNextPage = useCallback(() => {
    setPage((prev) => prev + 1);
  }, []);

  const reset = useCallback(() => {
    setData(initialData);
    setLoading(false);
    setError(null);
    setPage(1);
    setTotal(0);
  }, [initialData]);

  return {
    data,
    loading,
    error,
    refetch,
    page,
    pageSize,
    total,
    setPage,
    loadNextPage,
    reset,
  };
}
