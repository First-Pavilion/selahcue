/**
 * Which element a `UiButton` renders, and which attributes it gets. Pure, so node can test
 * the one decision that has been wrong twice:
 *
 *  1. (round 1) a router link was given `href: undefined`, which overrode the router's own
 *     href and left an `<a>` with no destination, unreachable from the keyboard.
 *  2. (round 2) a DISABLED link was still keyboard-operable: `aria-disabled` only TELLS
 *     assistive technology; `pointer-events: none` only stops the mouse. A real `href` is
 *     what makes an `<a>` focusable and activatable, so a disabled (or loading) link is
 *     rendered WITHOUT one: an `<a role="link" aria-disabled="true">` that Tab skips and
 *     Enter cannot follow. That is the standard disabled-link pattern.
 *
 * A native `<button>` just gets `disabled`, which the browser enforces.
 */
export interface ButtonInput {
  readonly to?: string | object
  readonly href?: string
  readonly disabled?: boolean
  readonly loading?: boolean
}

export interface ButtonElement {
  readonly tag: 'router-link' | 'a' | 'button'
  readonly attrs: Readonly<Record<string, unknown>>
}

export function buttonElement(input: ButtonInput): ButtonElement {
  const inert = input.disabled === true || input.loading === true
  const isLink = Boolean(input.to) || Boolean(input.href)
  if (isLink && inert) return { tag: 'a', attrs: { role: 'link', 'aria-disabled': 'true' } }
  if (input.to) return { tag: 'router-link', attrs: { to: input.to } }
  if (input.href) return { tag: 'a', attrs: { href: input.href } }
  return { tag: 'button', attrs: { disabled: inert } }
}
