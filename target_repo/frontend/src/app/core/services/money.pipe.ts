/**
 * MoneyPipe — formats integer satang as a THB string at the VIEW layer only
 * (context.md §4: money is integer minor units everywhere; format at the edge).
 */
import { Pipe, PipeTransform } from '@angular/core';

@Pipe({ name: 'thb', standalone: true })
export class MoneyPipe implements PipeTransform {
  transform(satang: number | null | undefined): string {
    const v = Math.trunc(satang ?? 0);
    const baht = Math.floor(Math.abs(v) / 100);
    const sub = Math.abs(v) % 100;
    const sign = v < 0 ? '-' : '';
    return `${sign}฿${baht.toLocaleString('en-US')}.${sub.toString().padStart(2, '0')}`;
  }
}
