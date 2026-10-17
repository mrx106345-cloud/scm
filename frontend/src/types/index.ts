// Shared TypeScript types for SCM Agent frontend

export interface User {
  id: string;
  username: string;
  email: string;
  role: 'admin' | 'technician' | ' Viewer';
  firstName: string;
  lastName: string;
  avatarUrl?: string;
  createdAt: string;
  updatedAt: string;
}

export type UserRole = User['role'];

export interface APIResponse<T> {
  success: boolean;
  data?: T;
  error?: string;
  meta?: Record<string, unknown>;
}

export interface PaginatedResponse<T> extends APIResponse<T[]> {
  page: number;
  pageSize: number;
  totalPages: number;
  totalItems: number;
  hasNext: boolean;
  hasPrev: boolean;
}

export interface Alert {
  id: string;
  type: 'stockout' | 'delay' | 'low_stock' | 'supplier_issues' | 'system';
  severity: 'critical' | 'warning' | 'info';
  title: string;
  description: string;
  itemId?: string;
  supplierId?: string;
  createdAt: string;
  resolvedAt?: string;
  read: boolean;
  relatedEntities?: Record<string, unknown>;
}

export interface Supplier {
  id: string;
  name: string;
  code: string;
  status: 'active' | 'inactive' | 'pending';
  contactEmail: string;
  contactPhone?: string;
  address: string;
  leadTimeDays: number;
  reliabilityScore: number;
  lastIssueDate?: string;
  createdAt: string;
  updatedAt: string;
}

export interface Item {
  id: string;
  sku: string;
  name: string;
  uom: string;
  category: string | null;
  criticality: string;
  unit_cost: string | null;
  moq: number;
  lot_multiple: number;
  stockout_cost: string | null;
  service_level: number | null;
  status: 'in_stock' | 'low_stock' | 'out_of_stock' | 'discontinued';
  forecast: Record<string, unknown> | null;
  alert_history: Array<{
    id: string;
    type: string;
    severity: string;
    status: string;
    score: string;
    expected_loss: string;
    created_at: string | null;
  }>;
  open_pos: Array<{
    po_id: string;
    po_number: string | null;
    supplier_id: string;
    status: string;
    order_date: string | null;
    promised_date: string | null;
    qty_ordered: string;
  }>;
}

export type SupplierRow = {
  id: string;
  code: string;
  name: string;
  active: boolean;
  contract_lead_time_days: number | null;
  risk_score: number | null;
  on_time_rate: number | null;
  mean_lt_recent: number | null;
  drift_pct: number | null;
  trend_flag: boolean | null;
};

export type SupplierDetail = {
  id: string;
  code: string;
  name: string;
  active: boolean;
  contract_lead_time_days: number | null;
  metrics: Record<string, unknown> | null;
  risk_breakdown: Record<string, number> | null;
  lead_time_trend: Array<{ receipt_date: string | null; lead_days: number }>;
  items_exposed: Array<{
    item_id: string;
    sku: string;
    name: string;
    criticality: string;
    po_number: string | null;
    po_status: string | null;
    qty_ordered: string;
  }>;
};

export type ItemDetail = Item;

export interface StockLevel {
  itemId: string;
  sku: string;
  quantity: number;
  threshold: number;
  status: 'healthy' | 'warning' | 'critical';
}

export interface Forecast {
  itemId: string;
  sku: string;
  period: string;
  demand: number;
  confidence: number;
  trend: 'up' | 'down' | 'stable';
  recommendation: string;
}

export interface ChatMessage {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  timestamp: string;
  references?: ChatReference[];
}

export interface ChatReference {
  type: 'item' | 'supplier' | 'alert';
  id: string;
  title: string;
  url: string;
}

export interface SupplierRecommendation {
  supplierId: string;
  supplierName: string;
  score: number;
  reason: string;
  projectedCost: string;
  leadTimeDays: number;
}

export interface DashboardStats {
  totalItems: number;
  totalSuppliers: number;
  activeAlerts: number;
  stockoutAlerts: number;
  criticalAlerts: number;
  avgLeadTime: number;
  avgReliability: number;
  lowStockItems: number;
  outOfStockItems: number;
  trend: 'up' | 'down' | 'stable';
}

export interface DashboardChartData {
  label: string;
  value: number;
  unit: string;
  trend: 'up' | 'down' | 'stable';
}

export interface AlarmMessage {
  id: string;
  type: 'stockout' | 'delay' | 'low_stock' | 'supplier_issues';
  severity: 'critical' | 'warning' | 'info';
  message: string;
  timestamp: string;
}

export interface Toast {
  id: string;
  type: 'success' | 'error' | 'warning' | 'info';
  title: string;
  description?: string;
  duration?: number;
  dismissible?: boolean;
}
