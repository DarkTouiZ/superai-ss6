/** Avatar — canonical round initials badge (e.g. courier/customer). */
import { Component, Input } from '@angular/core';

@Component({
  selector: 'e7-avatar',
  standalone: true,
  template: `<span class="e7-avatar" [attr.aria-label]="name">{{ initials }}</span>`,
  styles: [
    `
      .e7-avatar {
        display: inline-flex;
        align-items: center;
        justify-content: center;
        width: 36px;
        height: 36px;
        border-radius: 50%;
        background: var(--color-brand-dark);
        color: var(--color-text-inverse);
        font-size: var(--font-size-caption);
        font-weight: 700;
      }
    `,
  ],
})
export class AvatarComponent {
  @Input() name = '';

  get initials(): string {
    return this.name
      .split(/\s+/)
      .filter(Boolean)
      .slice(0, 2)
      .map((w) => w[0]?.toUpperCase() ?? '')
      .join('');
  }
}
