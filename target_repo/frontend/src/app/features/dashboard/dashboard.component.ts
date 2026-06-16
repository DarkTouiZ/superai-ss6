/**
 * Dashboard — revenue KPIs + top products. Composes the canonical MetricTile/Card
 * primitives and pulls data through ApiService. Degrades gracefully with no data.
 */
import { Component, OnInit, inject } from '@angular/core';
import { NgFor, NgIf } from '@angular/common';
import { ApiService, RevenueSummary } from '../../core/services/api.service';
import { MoneyPipe } from '../../core/services/money.pipe';
import { MetricTileComponent } from '../../shared/components/metric-tile/metric-tile.component';
import { CardComponent } from '../../shared/components/card/card.component';

@Component({
  selector: 'e7-dashboard',
  standalone: true,
  imports: [NgFor, NgIf, MoneyPipe, MetricTileComponent, CardComponent],
  template: `
    <h1>Today at eleven-7</h1>

    <div class="tiles" *ngIf="summary; else loading">
      <e7-metric-tile label="Orders" [value]="summary.totals.orders"></e7-metric-tile>
      <e7-metric-tile
        label="Gross revenue"
        [value]="summary.totals.gross_satang | thb"
        hint="excludes cancelled"
      ></e7-metric-tile>
      <e7-metric-tile
        label="Delivered revenue"
        [value]="summary.totals.delivered_satang | thb"
      ></e7-metric-tile>
    </div>

    <e7-card *ngIf="summary && summary.topProducts.length; else noProducts">
      <h3>Top products by revenue</h3>
      <table>
        <tr *ngFor="let p of summary.topProducts">
          <td>{{ p.product_name }}</td>
          <td class="num">{{ p.units }} units</td>
          <td class="num">{{ p.revenue_satang | thb }}</td>
        </tr>
      </table>
    </e7-card>

    <ng-template #noProducts>
      <e7-card *ngIf="summary"><p class="empty">No sales yet today.</p></e7-card>
    </ng-template>
    <ng-template #loading><p class="empty">Loading…</p></ng-template>
  `,
  styles: [
    `
      h1 { font-size: var(--font-size-display); margin-bottom: var(--space-lg); }
      .tiles { display: grid; grid-template-columns: repeat(3, 1fr); gap: var(--space-md); margin-bottom: var(--space-lg); }
      table { width: 100%; border-collapse: collapse; margin-top: var(--space-sm); }
      td { padding: var(--space-sm) 0; border-bottom: 1px solid var(--color-border); }
      .num { text-align: right; color: var(--color-text-secondary); }
      .empty { color: var(--color-text-secondary); }
    `,
  ],
})
export class DashboardComponent implements OnInit {
  private readonly api = inject(ApiService);
  summary: RevenueSummary | null = null;

  ngOnInit(): void {
    this.api.getRevenueSummary().subscribe((s) => (this.summary = s));
  }
}
