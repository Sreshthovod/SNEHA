// @vitest-environment node
import { execFileSync } from 'node:child_process'
import { join } from 'node:path'
import { describe, expect, it } from 'vitest'

describe('generated API types', () => {
  it('src/api/schema.d.ts matches packages/api_contracts/openapi.json (run `npm run gen:api`)', () => {
    const root = join(import.meta.dirname, '..')
    const run = () =>
      execFileSync(
        join(root, 'node_modules', '.bin', 'openapi-typescript'),
        ['../../packages/api_contracts/openapi.json', '-o', 'src/api/schema.d.ts', '--default-non-nullable', 'false', '--check'],
        { cwd: root, stdio: 'pipe' },
      )
    expect(run).not.toThrow()
  })
})
