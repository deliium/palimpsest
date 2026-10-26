export type GenerationMarker = {
  generation_index: number
  first_entry_tick: number
  seek_tick: number
  admitted_count: number
  label_code: 'founders' | 'generation_first_admission'
}
