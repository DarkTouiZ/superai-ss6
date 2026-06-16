/** App shell — top nav + router outlet for the eleven-7 ops console. */
import { Component } from '@angular/core';
import { RouterLink, RouterLinkActive, RouterOutlet } from '@angular/router';

@Component({
  selector: 'e7-root',
  standalone: true,
  imports: [RouterOutlet, RouterLink, RouterLinkActive],
  template: `
    <header class="topbar">
      <span class="brand">eleven<span class="dash">-</span>7</span>
      <nav>
        <a routerLink="/dashboard" routerLinkActive="active">Dashboard</a>
        <a routerLink="/catalog" routerLinkActive="active">Catalog</a>
        <a routerLink="/orders" routerLinkActive="active">Orders</a>
        <a routerLink="/deliveries" routerLinkActive="active">Deliveries</a>
      </nav>
    </header>
    <main class="content"><router-outlet></router-outlet></main>
  `,
  styles: [
    `
      .topbar {
        display: flex;
        align-items: center;
        gap: var(--space-xl);
        background: var(--color-brand);
        color: var(--color-text-inverse);
        padding: var(--space-md) var(--space-lg);
      }
      .brand { font-size: var(--font-size-title); font-weight: 800; }
      .brand .dash { color: var(--color-accent); }
      nav { display: flex; gap: var(--space-lg); }
      nav a { color: var(--color-text-inverse); text-decoration: none; opacity: 0.85; font-weight: 600; }
      nav a.active { opacity: 1; border-bottom: 2px solid var(--color-accent); }
      .content { padding: var(--space-lg); max-width: 1100px; margin: 0 auto; }
    `,
  ],
})
export class AppComponent {}
