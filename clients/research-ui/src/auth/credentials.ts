/** Per-capability credential slots (header-only; never query strings). */

export type CapabilitySlot =
  | 'simulation_control'
  | 'objective_inspection'
  | 'agent_visible'
  | 'subjective_debug'

const STORAGE_KEY = 'palimpsest.research_ui.credentials.v1'

const SECRET_QUERY_KEYS = new Set([
  'token',
  'credential',
  'credentials',
  'secret',
  'api_key',
  'apikey',
  'authorization',
  'password',
  'access_token',
])

export type CredentialStore = Record<CapabilitySlot, string>

const EMPTY: CredentialStore = {
  simulation_control: '',
  objective_inspection: '',
  agent_visible: '',
  subjective_debug: '',
}

let memory: CredentialStore = { ...EMPTY }

export function loadCredentials(): CredentialStore {
  try {
    const raw = sessionStorage.getItem(STORAGE_KEY)
    if (raw === null) {
      return { ...memory }
    }
    const parsed = JSON.parse(raw) as Partial<CredentialStore>
    memory = {
      simulation_control: String(parsed.simulation_control ?? ''),
      objective_inspection: String(parsed.objective_inspection ?? ''),
      agent_visible: String(parsed.agent_visible ?? ''),
      subjective_debug: String(parsed.subjective_debug ?? ''),
    }
  } catch {
    memory = { ...EMPTY }
  }
  return { ...memory }
}

export function saveCredentials(next: CredentialStore): void {
  memory = { ...next }
  try {
    sessionStorage.setItem(STORAGE_KEY, JSON.stringify(memory))
  } catch {
    // sessionStorage may be unavailable; keep in-memory only
  }
}

export function credentialFor(capability: CapabilitySlot): string | null {
  const store = loadCredentials()
  const value = store[capability].trim()
  return value === '' ? null : value
}

/** Strip banned secret keys from a URL search string; WARN in DEV. */
export function stripSecretQueryKeys(search: string): {
  cleaned: string
  stripped: string[]
} {
  const text = search.startsWith('?') ? search.slice(1) : search
  const params = new URLSearchParams(text)
  const stripped: string[] = []
  for (const key of [...params.keys()]) {
    if (SECRET_QUERY_KEYS.has(key.toLowerCase())) {
      params.delete(key)
      stripped.push(key)
    }
  }
  if (stripped.length > 0 && import.meta.env.DEV) {
    console.warn(
      `research_ui_auth_secret_stripped keys=${stripped.join(',')}`,
    )
  }
  const cleaned = params.toString()
  return { cleaned: cleaned === '' ? '' : `?${cleaned}`, stripped }
}

export const CAPABILITY_LABELS: Record<CapabilitySlot, string> = {
  simulation_control: 'Control',
  objective_inspection: 'Inspection',
  agent_visible: 'Agent-visible',
  subjective_debug: 'Debug',
}
