import { readdirSync, statSync } from 'node:fs'
import { join } from 'node:path'

const dist = new URL('../dist/', import.meta.url)
const root = dist.pathname

function countFiles(dir) {
  let count = 0
  for (const name of readdirSync(dir)) {
    const path = join(dir, name)
    const st = statSync(path)
    if (st.isDirectory()) {
      count += countFiles(path)
    } else if (st.isFile()) {
      count += 1
    }
  }
  return count
}

try {
  const fileCount = countFiles(root)
  console.log(`INFO research_ui_build_ok file_count=${fileCount}`)
} catch (err) {
  const reason =
    err && typeof err === 'object' && 'code' in err ? String(err.code) : 'build_report_failed'
  console.error(`ERROR research_ui_build_failed reason_code=${reason}`)
  process.exit(1)
}
