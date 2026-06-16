/** MetricTile — canonical KPI tile for dashboards. Composes Card. */
import { Component, Input } from '@angular/core';
import { NgIf } from '@angular/common';
import { CardComponent } from '../card/card.component';

@Component({
  selector: 'e7-metric-tile',
  standalone: true,
  imports: [CardComponent, NgIf],
  template: `
    <e7-card>
      <div class="label">{{ label }}</div>
      <div class="value">{{ value }}</div>
      <div class="hint" *ngIf="hint">{{ hint }}</div>
    </e7-card>
  `,
  styles: [
    `
      .label { color: var(--color-text-secondary); font-size: var(--font-size-caption); text-transform: uppercase; letter-spacing: 0.04em; }
      .value { font-size: var(--font-size-display); font-weight: 700; margin-top: var(--space-xs); }
      .hint  { color: var(--color-text-secondary); font-size: var(--font-size-caption); margin-top: var(--space-xs); }
    `,
  ],
})
export class MetricTileComponent {
  @Input() label = '';
  @Input() value: string | number = '';
  @Input() hint?: string;
}
