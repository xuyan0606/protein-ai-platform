import { copyFileSync, mkdirSync, statSync } from 'node:fs'
import { dirname } from 'node:path'
import { fileURLToPath } from 'node:url'

const source = fileURLToPath(new URL('../node_modules/3dmol/build/3Dmol.js', import.meta.url))
const target = fileURLToPath(new URL('../public/vendor/3Dmol.js', import.meta.url))

statSync(source)
mkdirSync(dirname(target), { recursive: true })
copyFileSync(source, target)
