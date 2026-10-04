import { mount } from 'svelte'
import App from './App.svelte'
import './app.css'

const target = document.getElementById('app')
if (target === null) {
  throw new Error('research_ui_boot_failed reason_code=missing_app_root')
}

const app = mount(App, { target })

export default app
