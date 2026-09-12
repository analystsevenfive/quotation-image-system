import * as React from 'react';
import { Slot } from '@radix-ui/react-slot';
import { cva, type VariantProps } from 'class-variance-authority';
import { cn } from '@/lib/utils';
const variants = cva('inline-flex items-center justify-center gap-2 rounded-[14px] text-sm font-semibold transition-all focus-visible:outline-2 focus-visible:outline-offset-4 focus-visible:outline-[var(--brand)] disabled:pointer-events-none disabled:opacity-50 active:scale-[0.99]', {
  variants: {
    variant: {
      default: 'bg-[var(--brand)] text-white hover:bg-[var(--brand-strong)] shadow-sm hover:shadow',
      destructive: 'bg-[var(--danger)] text-white hover:bg-[#991b1b] shadow-sm',
      outline: 'border border-[var(--border)] bg-[var(--surface)] text-[var(--text)] hover:bg-[var(--brand-soft)] hover:text-[var(--brand-strong)] hover:border-[var(--brand)]',
      ghost: 'text-[var(--muted)] hover:bg-[var(--brand-soft)] hover:text-[var(--brand-strong)]',
      accent: 'bg-[var(--accent)] text-[#13231e] hover:brightness-95 shadow-sm'
    },
    size: {
      default: 'h-11 px-5',
      sm: 'h-9 px-3.5 text-xs',
      icon: 'h-10 w-10'
    }
  },
  defaultVariants: {variant: 'default', size: 'default'},
});
export function Button({className, variant, size, asChild = false, ...props}: React.ComponentProps<'button'> & VariantProps<typeof variants> & {asChild?: boolean}) {
  const Comp = asChild ? Slot : 'button';
  return <Comp className={cn(variants({variant, size, className}))} {...props} />;
}
