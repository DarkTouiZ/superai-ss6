/** Badge — canonical status pill. Variant maps to a token color. */
import { Component, Input } from '@angular/core';
import { NgClass } from '@angular/common';

export type BadgeVariant = 'neutral' | 'success' | 'warning' | 'danger' | 'brand';

@Component({
  selector: 'e7-badge',
  standalone: true,
  imports: [NgClass],
  template: `<span class="e7-badge" [ngClass]="'v-' + variant"><ng-content></ng-content></span>`,
  styles: [
    `
      .e7-badge {
        display: inline-block;
        padding: var(--space-xs) var(--space-sm);
        border-radius: var(--radius-sm);
        font-size: var(--font-size-caption);
        font-weight: 600;
        color: var(--color-text-inverse);
      }
      .v-neutral { background: var(--color-text-secondary); }
      .v-success { background: var(--color-success); }
      .v-warning { background: var(--color-warning); }
      .v-danger  { background: var(--color-danger); }
      .v-brand   { background: var(--color-brand); }
    `,
  ],
})
export class BadgeComponent {
  @Input() variant: BadgeVariant = 'neutral';
}
