/** Deliveries — courier roster with availability. Composes Card + Avatar + Badge. */
import { Component, OnInit, inject } from '@angular/core';
import { NgFor, NgIf } from '@angular/common';
import { ApiService, Courier } from '../../core/services/api.service';
import { CardComponent } from '../../shared/components/card/card.component';
import { AvatarComponent } from '../../shared/components/avatar/avatar.component';
import { BadgeComponent, BadgeVariant } from '../../shared/components/badge/badge.component';

@Component({
  selector: 'e7-deliveries',
  standalone: true,
  imports: [NgFor, NgIf, CardComponent, AvatarComponent, BadgeComponent],
  template: `
    <h1>Couriers</h1>
    <div class="list" *ngIf="couriers.length; else empty">
      <e7-card *ngFor="let c of couriers">
        <div class="row">
          <e7-avatar [name]="c.full_name"></e7-avatar>
          <div class="meta">
            <strong>{{ c.full_name }}</strong>
            <div class="sub">{{ c.vehicle }} · {{ c.zone }} · ★ {{ c.rating }}</div>
          </div>
          <e7-badge [variant]="statusVariant(c.status)">{{ c.status }}</e7-badge>
        </div>
      </e7-card>
    </div>
    <ng-template #empty><p class="muted">No couriers on shift.</p></ng-template>
  `,
  styles: [
    `
      h1 { font-size: var(--font-size-display); margin-bottom: var(--space-lg); }
      .list { display: grid; grid-template-columns: repeat(auto-fill, minmax(280px, 1fr)); gap: var(--space-md); }
      .row { display: flex; align-items: center; gap: var(--space-md); }
      .meta { flex: 1; }
      .sub { color: var(--color-text-secondary); font-size: var(--font-size-caption); }
      .muted { color: var(--color-text-secondary); }
    `,
  ],
})
export class DeliveriesComponent implements OnInit {
  private readonly api = inject(ApiService);
  couriers: Courier[] = [];

  ngOnInit(): void {
    this.api.getCouriers().subscribe((r) => (this.couriers = r.couriers));
  }

  statusVariant(status: string): BadgeVariant {
    switch (status) {
      case 'available':
        return 'success';
      case 'on_delivery':
        return 'warning';
      case 'offline':
        return 'danger';
      default:
        return 'neutral';
    }
  }
}
