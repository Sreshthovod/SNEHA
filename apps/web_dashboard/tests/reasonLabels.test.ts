// @vitest-environment node
// Every reason code the engine can produce has caregiver-facing wording, so the dashboard
// never shows a raw code. Reads the engine source (the source of truth) and the label table.
import { readFileSync } from 'node:fs'
import { join } from 'node:path'
import { describe, expect, it } from 'vitest'

const root = join(import.meta.dirname, '..')
const engine = readFileSync(join(root, '../../services/api/app/personalization/engine.py'), 'utf8')
const labels = readFileSync(join(root, 'src/lib/personalization.ts'), 'utf8')

const reasonBlock = engine.slice(engine.indexOf('class Reason(StrEnum):'), engine.indexOf('class Action(StrEnum):'))
const codes = [...reasonBlock.matchAll(/= "([A-Z_]+)"/g)].map((m) => m[1])
const table = labels.slice(labels.indexOf('REASON_LABELS'), labels.indexOf('export function reasonLabel'))
const labelled = new Map([...table.matchAll(/^\s+([A-Z_]+): ['"](.+)['"],$/gm)].map((m) => [m[1], m[2]]))

describe('engine reason labels', () => {
  it('finds the engine reason codes', () => {
    expect(codes.length).toBeGreaterThan(25)
    expect(codes).toContain('INSTRUCTIONS_READ_ALOUD_FIRST')
  })

  it('has plain-language wording for every code, without diagnostic language', () => {
    expect(codes.filter((c) => !labelled.has(c))).toEqual([])
    for (const text of labelled.values()) expect(text).not.toMatch(/dementia|decline|diagnos/i)
  })
})
