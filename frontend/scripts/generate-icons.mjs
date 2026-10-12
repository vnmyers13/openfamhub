import { Resvg } from '@resvg/resvg-js'
import { readFileSync, writeFileSync } from 'node:fs'
import { dirname, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'

const here = dirname(fileURLToPath(import.meta.url))
const iconsDir = resolve(here, '..', 'public', 'icons')
const svg = (name) => readFileSync(resolve(iconsDir, name), 'utf8')
const render = (src, size) => new Resvg(src, { fitTo: { mode: 'width', value: size } }).render().asPng()

const jobs = [
  ['icon-app.svg', 192, 'icon-192.png'],
  ['icon-app.svg', 512, 'icon-512.png'],
  ['icon-maskable.svg', 512, 'maskable-icon-512.png'],
  ['icon-maskable.svg', 180, 'apple-touch-icon-180x180.png'],
]

for (const [src, size, out] of jobs) {
  const png = render(svg(src), size)
  writeFileSync(resolve(iconsDir, out), png)
  console.log(`${out}: ${png.length} bytes`)
}
