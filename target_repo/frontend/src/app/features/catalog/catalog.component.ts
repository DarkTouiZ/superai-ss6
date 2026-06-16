/** Catalog — product grid. Composes Card + Badge + MoneyPipe. */
import { Component, OnInit, inject } from '@angular/core';
import { NgFor, NgIf } from '@angular/common';
import { ApiService, Product } from '../../core/services/api.service';
import { MoneyPipe } from '../../core/services/money.pipe';
import { CardComponent } from '../../shared/components/card/card.component';
import { BadgeComponent } from '../../shared/components/badge/badge.component';

@Component({
  selector: 'e7-catalog',
  standalone: true,
  imports: [NgFor, NgIf, MoneyPipe, CardComponent, BadgeComponent],
  template: `
    <h1>Catalog</h1>
    <div class="grid" *ngIf="products.length; else empty">
      <e7-card *ngFor="let p of products">
        <div class="row">
          <strong>{{ p.name }}</strong>
          <e7-badge variant="brand">{{ p.unit }}</e7-badge>
        </div>
        <div class="sku">{{ p.sku }}</div>
        <div class="price">{{ p.price_satang | thb }}</div>
      </e7-card>
    </div>
    <ng-template #empty><p class="muted">No products available.</p></ng-template>
  `,
  styles: [
    `
      h1 { font-size: var(--font-size-display); margin-bottom: var(--space-lg); }
      .grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(220px, 1fr)); gap: var(--space-md); }
      .row { display: flex; justify-content: space-between; align-items: center; gap: var(--space-sm); }
      .sku { color: var(--color-text-secondary); font-size: var(--font-size-caption); margin: var(--space-xs) 0; }
      .price { font-size: var(--font-size-title); font-weight: 700; color: var(--color-brand-dark); }
      .muted { color: var(--color-text-secondary); }
    `,
  ],
})
export class CatalogComponent implements OnInit {
  private readonly api = inject(ApiService);
  products: Product[] = [];

  ngOnInit(): void {
    this.api.getProducts().subscribe((r) => (this.products = r.products));
  }
}
