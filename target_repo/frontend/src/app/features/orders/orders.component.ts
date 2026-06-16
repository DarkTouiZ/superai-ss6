/** Orders — recent orders list with a status badge. Composes Card + Badge. */
import { Component, OnInit, inject } from '@angular/core';
import { NgFor, NgIf } from '@angular/common';
import { ApiService, OrderSummary } from '../../core/services/api.service';
import { MoneyPipe } from '../../core/services/money.pipe';
import { CardComponent } from '../../shared/components/card/card.component';
import { BadgeComponent, BadgeVariant } from '../../shared/components/badge/badge.component';

@Component({
  selector: 'e7-orders',
  standalone: true,
  imports: [NgFor, NgIf, MoneyPipe, CardComponent, BadgeComponent],
  template: `
    <h1>Orders</h1>
    <e7-card *ngIf="orders.length; else empty">
      <table>
        <thead>
          <tr><th>Order</th><th>Type</th><th>Status</th><th class="num">Total</th></tr>
        </thead>
        <tbody>
          <tr *ngFor="let o of orders">
            <td>{{ o.order_no }}</td>
            <td>{{ o.fulfillment_type }}</td>
            <td><e7-badge [variant]="statusVariant(o.status)">{{ o.status }}</e7-badge></td>
            <td class="num">{{ o.total_satang | thb }}</td>
          </tr>
        </tbody>
      </table>
    </e7-card>
    <ng-template #empty><p class="muted">No orders yet.</p></ng-template>
  `,
  styles: [
    `
      h1 { font-size: var(--font-size-display); margin-bottom: var(--space-lg); }
      table { width: 100%; border-collapse: collapse; }
      th, td { text-align: left; padding: var(--space-sm); border-bottom: 1px solid var(--color-border); }
      th { color: var(--color-text-secondary); font-size: var(--font-size-caption); text-transform: uppercase; }
      .num { text-align: right; }
      .muted { color: var(--color-text-secondary); }
    `,
  ],
})
export class OrdersComponent implements OnInit {
  private readonly api = inject(ApiService);
  orders: OrderSummary[] = [];

  ngOnInit(): void {
    this.api.getOrders().subscribe((r) => (this.orders = r.orders));
  }

  statusVariant(status: string): BadgeVariant {
    switch (status) {
      case 'delivered':
        return 'success';
      case 'cancelled':
        return 'danger';
      case 'dispatched':
      case 'preparing':
        return 'warning';
      default:
        return 'neutral';
    }
  }
}
