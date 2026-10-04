/**
 * A minimal PNG reader for the tests that have to look at pixels: 8-bit, non-interlaced RGB or RGBA
 * (the logo file and the committed Figma reference frames are both RGBA). No dependencies: `node:zlib`
 * inflates, the five scanline filters are undone here. It refuses anything else rather than guessing,
 * so a re-exported logo in another format fails loudly instead of being read as noise.
 *
 * `maxRows` stops after that many scanlines: a filter depends only on the rows ABOVE it, so a crop near
 * the top of a 6,800px reference frame costs a few rows, not the whole 39MB.
 */
import { inflateSync } from 'node:zlib'

export interface Png {
  readonly width: number
  readonly height: number
  /** Rows actually decoded (<= height). */
  readonly rows: number
  readonly channels: 3 | 4
  /** `rows * width * channels` bytes, row-major. */
  readonly data: Uint8Array
}

const SIGNATURE = [0x89, 0x50, 0x4e, 0x47, 0x0d, 0x0a, 0x1a, 0x0a]

export function decodePng(file: Uint8Array, maxRows = Number.POSITIVE_INFINITY): Png {
  if (!SIGNATURE.every((byte, i) => file[i] === byte)) throw new Error('not a PNG')
  const view = new DataView(file.buffer, file.byteOffset, file.byteLength)
  let width = 0
  let height = 0
  let channels: 3 | 4 = 4
  const idat: Uint8Array[] = []
  for (let at = 8; at < file.length; ) {
    const length = view.getUint32(at)
    const type = String.fromCharCode(...file.subarray(at + 4, at + 8))
    const body = file.subarray(at + 8, at + 8 + length)
    if (type === 'IHDR') {
      width = view.getUint32(at + 8)
      height = view.getUint32(at + 12)
      const [depth, colorType, , , interlace] = [body[8], body[9], body[10], body[11], body[12]]
      if (depth !== 8 || interlace !== 0 || (colorType !== 6 && colorType !== 2)) {
        throw new Error(`unsupported PNG (depth ${depth}, colour type ${colorType}, interlace ${interlace}): 8-bit RGB/RGBA only`)
      }
      channels = colorType === 6 ? 4 : 3
    } else if (type === 'IDAT') idat.push(body)
    else if (type === 'IEND') break
    at += 12 + length
  }
  const stride = width * channels
  const rows = Math.min(height, maxRows)
  const raw = inflateSync(Buffer.concat(idat))
  const data = new Uint8Array(rows * stride)
  for (let y = 0; y < rows; y++) {
    const filter = raw[y * (stride + 1)]
    const src = y * (stride + 1) + 1
    const row = y * stride
    for (let x = 0; x < stride; x++) {
      const a = x >= channels ? (data[row + x - channels] as number) : 0
      const b = y > 0 ? (data[row - stride + x] as number) : 0
      const c = y > 0 && x >= channels ? (data[row - stride + x - channels] as number) : 0
      let predictor = 0
      if (filter === 1) predictor = a
      else if (filter === 2) predictor = b
      else if (filter === 3) predictor = (a + b) >> 1
      else if (filter === 4) {
        const p = a + b - c
        const pa = Math.abs(p - a)
        const pb = Math.abs(p - b)
        const pc = Math.abs(p - c)
        predictor = pa <= pb && pa <= pc ? a : pb <= pc ? b : c
      } else if (filter !== 0) throw new Error(`bad PNG filter ${filter}`)
      data[row + x] = ((raw[src + x] as number) + predictor) & 255
    }
  }
  return { width, height, rows, channels, data }
}

export interface Box {
  readonly x0: number
  readonly y0: number
  /** exclusive */
  readonly x1: number
  readonly y1: number
}

/** The bounding box of every pixel whose alpha exceeds `threshold` (the artwork inside its padding). */
export function alphaBox(png: Png, threshold = 8): Box {
  if (png.channels !== 4) throw new Error('no alpha channel')
  let x0 = png.width
  let y0 = png.rows
  let x1 = -1
  let y1 = -1
  for (let y = 0; y < png.rows; y++) {
    for (let x = 0; x < png.width; x++) {
      if ((png.data[(y * png.width + x) * 4 + 3] as number) > threshold) {
        if (x < x0) x0 = x
        if (x > x1) x1 = x
        if (y < y0) y0 = y
        y1 = y
      }
    }
  }
  if (x1 < 0) throw new Error('fully transparent')
  return { x0, y0, x1: x1 + 1, y1: y1 + 1 }
}

/**
 * The bounding box of the "ink" in a region of a rendered frame: every pixel whose colour differs from the
 * region's own top-left pixel (the background) by more than `threshold` on some channel. Absolute coordinates.
 */
export function inkBox(png: Png, region: Box, threshold = 40): Box {
  const at = (x: number, y: number, c: number) => png.data[(y * png.width + x) * png.channels + c] as number
  const bg = [0, 1, 2].map((c) => at(region.x0, region.y0, c))
  let x0 = region.x1
  let y0 = region.y1
  let x1 = -1
  let y1 = -1
  for (let y = region.y0; y < region.y1; y++) {
    for (let x = region.x0; x < region.x1; x++) {
      if ([0, 1, 2].some((c) => Math.abs(at(x, y, c) - (bg[c] as number)) > threshold)) {
        if (x < x0) x0 = x
        if (x > x1) x1 = x
        if (y < y0) y0 = y
        y1 = y
      }
    }
  }
  if (x1 < 0) throw new Error('no ink in the region')
  return { x0, y0, x1: x1 + 1, y1: y1 + 1 }
}
