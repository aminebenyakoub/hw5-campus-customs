import { useEffect, useRef, useState } from 'react'
import { money } from '../agents'
import type { Cash } from '../types'

/** Checking balance that counts down when money goes out, with a "−$X" drop tag. */
export function CashMeter({ cash }: { cash: Cash | null }) {
  const target = cash?.balance ?? 0
  const [shown, setShown] = useState(target)
  const [drop, setDrop] = useState<{ amount: number; key: number } | null>(null)
  const prev = useRef<number | null>(null)

  useEffect(() => {
    if (cash === null) return
    const from = prev.current ?? target
    prev.current = target
    if (from === target) {
      setShown(target)
      return
    }
    if (target < from) setDrop({ amount: from - target, key: Date.now() })
    const start = performance.now()
    const ms = 900
    let raf = 0
    const tick = (now: number) => {
      const t = Math.min(1, (now - start) / ms)
      const ease = 1 - Math.pow(1 - t, 3)
      setShown(from + (target - from) * ease)
      if (t < 1) raf = requestAnimationFrame(tick)
    }
    raf = requestAnimationFrame(tick)
    return () => cancelAnimationFrame(raf)
  }, [target, cash])

  if (!cash) return <div className="cash cash--empty">Checking —</div>

  const committed = Math.min(cash.requested_not_paid, cash.balance)
  const pctCommitted = cash.balance > 0 ? (committed / cash.balance) * 100 : 0

  return (
    <div className="cash" aria-live="polite">
      <div className="cash__label">Checking</div>
      <div className="cash__value">
        {money(shown)}
        {drop && (
          <span key={drop.key} className="cash__drop" onAnimationEnd={() => setDrop(null)}>
            −{money(drop.amount)}
          </span>
        )}
      </div>
      <div className="cash__bar" title="Share of checking already requested by agents">
        <span className="cash__bar-free" style={{ width: `${100 - pctCommitted}%` }} />
        <span className="cash__bar-held" style={{ width: `${pctCommitted}%` }} />
      </div>
      <div className="cash__sub">
        {cash.requested_not_paid > 0 ? (
          <>
            <b>{money(cash.requested_not_paid)}</b> waiting on approval · <b>{money(cash.balance_after_requests)}</b> if all paid
          </>
        ) : (
          'Nothing waiting on approval'
        )}
      </div>
    </div>
  )
}
