/** Card — canonical surface primitive. Compose screens from this, don't re-implement. */
import { Component } from '@angular/core';

@Component({
  selector: 'e7-card',
  standalone: true,
  template: `<div class="e7-card"><ng-content></ng-content></div>`,
  styles: [
    `
      .e7-card {
        background: var(--color-surface);
        border: 1px solid var(--color-border);
        border-radius: var(--radius-md);
        box-shadow: var(--shadow-card);
        padding: var(--space-md);
      }
    `,
  ],
})
export class CardComponent {}
