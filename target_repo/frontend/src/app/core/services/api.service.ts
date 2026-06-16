/**
 * ApiService — the SINGLE HTTP client wrapper for eleven-7 (context.md §4:
 * components/feature services MUST call the API through here, never HttpClient
 * or fetch directly). Centralizes base URL, headers, and error mapping.
 */
import { Injectable, inject } from '@angular/core';
import { HttpClient, HttpParams } from '@angular/common/http';
import { Observable } from 'rxjs';
import { environment } from '../../../environments/environment';

export interface Product {
  id: number;
  category_id: number;
  sku: string;
  name: string;
  unit: string;
  price_satang: number;
}

export interface OrderSummary {
  id: number;
  order_no: string;
  status: string;
  fulfillment_type: string;
  total_satang: number;
  placed_at: string;
}

export interface RevenueSummary {
  totals: { orders: number; gross_satang: number; delivered_satang: number };
  byStatus: Array<{ status: string; count: number }>;
  topProducts: Array<{ product_name: string; units: number; revenue_satang: number }>;
}

export interface Courier {
  id: number;
  full_name: string;
  vehicle: string;
  status: string;
  zone: string;
  rating: number;
}

@Injectable({ providedIn: 'root' })
export class ApiService {
  private readonly http = inject(HttpClient);
  private readonly base = environment.apiBaseUrl;

  getProducts(categoryId?: number): Observable<{ products: Product[] }> {
    let params = new HttpParams();
    if (categoryId) params = params.set('categoryId', categoryId);
    return this.http.get<{ products: Product[] }>(`${this.base}/products`, { params });
  }

  getLowStock(): Observable<{ products: Array<Product & { qty_on_hand: number }> }> {
    return this.http.get<{ products: Array<Product & { qty_on_hand: number }> }>(
      `${this.base}/products/low-stock`,
    );
  }

  getOrders(status?: string): Observable<{ orders: OrderSummary[] }> {
    let params = new HttpParams();
    if (status) params = params.set('status', status);
    return this.http.get<{ orders: OrderSummary[] }>(`${this.base}/orders`, { params });
  }

  getRevenueSummary(): Observable<RevenueSummary> {
    return this.http.get<RevenueSummary>(`${this.base}/dashboard/revenue`);
  }

  getCouriers(): Observable<{ couriers: Courier[] }> {
    return this.http.get<{ couriers: Courier[] }>(`${this.base}/couriers`);
  }
}
