/** Button — canonical action primitive. */
import { Component, Input } from '@angular/core';
import { NgClass } from '@angular/common';

@Component({
  selector: 'e7-button',
  standalone: true,
  imports: [NgClass],
  template: `
    <button class="e7-btn" [ngClass]="'v-' + variant" [disabled]="disabled" [attr.aria-label]="ariaLabel">
      <ng-content></ng-content>
    </button>
  `,
  styles: [
    `
      .e7-btn {
        border: none;
        border-radius: var(--radius-sm);
        padding: var(--space-sm) var(--space-md);
        font-size: var(--font-size-body);
        font-weight: 600;
        cursor: pointer;
        color: var(--color-text-inverse);
      }
      .e7-btn:disabled { opacity: 0.5; cursor: not-allowed; }
      .v-primary   { background: var(--color-brand); }
      .v-secondary { background: var(--color-text-secondary); }
      .v-accent    { background: var(--color-accent); }
    `,
  ],
})
export class ButtonComponent {
  @Input() variant: 'primary' | 'secondary' | 'accent' = 'primary';
  @Input() disabled = false;
  @Input() ariaLabel?: string;
}
