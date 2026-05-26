<template>
  <div v-if="widgetVisible" class="char-widget">

    <!-- キャラアイコン（チャット閉じてる時） -->
    <div v-if="!chatOpen" class="char-trigger" @click="openChat">
      <Transition name="bubble">
        <div v-if="bubble" class="speech-bubble">
          <span>{{ bubble }}</span>
        </div>
      </Transition>
      <div class="char-icon">
        <div v-html="avatarHtml(1)" class="pixel-art idle"></div>
      </div>
    </div>

    <!-- チャットウィンドウ -->
    <Transition name="chat-expand">
      <div v-if="chatOpen" class="chat-window">
        <div class="chat-header">
          <div v-html="avatarHtml(0.45)" class="pixel-art-sm"></div>
          <span class="char-name">{{ settings.name }}</span>
          <div class="header-acts">
            <button class="hbtn" @click="settingsOpen = true">⚙️</button>
            <button class="hbtn" @click="chatOpen = false">✕</button>
          </div>
        </div>

        <div class="chat-msgs" ref="messagesEl">
          <div v-if="messages.length === 0" class="chat-welcome">
            <div v-html="avatarHtml(1.2)" class="pixel-art idle"></div>
            <p class="welcome-text">{{ settings.greeting_morning }}</p>
            <div class="quick-btns">
              <button v-for="q in quickReplies" :key="q" class="quick-btn" @click="quickSend(q)">{{ q }}</button>
            </div>
          </div>
          <template v-else>
            <div
              v-for="(msg, i) in messages" :key="i"
              class="msg" :class="msg.role === 'user' ? 'msg-user' : 'msg-char'"
            >
              <div v-if="msg.role === 'assistant'" v-html="avatarHtml(0.4)" class="pixel-art-xs"></div>
              <div class="msg-bubble">{{ msg.content }}</div>
            </div>
          </template>
          <div v-if="loading" class="msg msg-char">
            <div v-html="avatarHtml(0.4)" class="pixel-art-xs"></div>
            <div class="msg-bubble typing"><span>●</span><span>●</span><span>●</span></div>
          </div>
        </div>

        <div class="input-row">
          <input
            v-model="inputText"
            @keydown.enter="sendMessage"
            placeholder="メッセージを入力..."
            class="chat-input"
            :disabled="loading"
          />
          <button @click="sendMessage" class="send-btn" :disabled="loading || !inputText.trim()">▶</button>
        </div>
      </div>
    </Transition>
  </div>

  <!-- 設定モーダル -->
  <Transition name="fade">
    <div v-if="settingsOpen" class="modal-overlay" @click.self="settingsOpen = false">
      <div class="settings-modal">
        <div class="modal-header">
          <span>キャラクター設定</span>
          <button class="hbtn" @click="settingsOpen = false">✕</button>
        </div>
        <div class="modal-body">
          <div class="field">
            <label>キャラクター選択</label>
            <div class="preset-grid">
              <button
                v-for="p in PRESET_AVATARS" :key="p.id"
                class="preset-btn"
                :class="{ active: editSettings.avatar_type === 'preset' && editSettings.avatar === p.src }"
                @click="editSettings.avatar_type = 'preset'; editSettings.avatar = p.src"
              >
                <img :src="p.src" :alt="p.label" class="preset-thumb" />
                <span class="preset-label">{{ p.label }}</span>
              </button>
            </div>
            <label style="margin-top:12px;display:block;font-size:12px;color:#888;">絵文字から選ぶ</label>
            <div class="emoji-grid">
              <button
                v-for="e in emojiPresets" :key="e"
                class="emoji-btn" :class="{ active: editSettings.avatar === e && editSettings.avatar_type === 'emoji' }"
                @click="selectEmoji(e)"
              >{{ e }}</button>
            </div>
            <label class="upload-label">
              📁 画像アップロード
              <input type="file" accept="image/*" @change="handleAvatarUpload" hidden />
            </label>
            <img v-if="editSettings.avatar_type === 'image'" :src="editSettings.avatar" class="avatar-preview" />
          </div>
          <div v-if="editSettings.avatar_type === 'pixel'" class="avatar-customizer">
            <div class="avatar-preview-panel">
              <div v-html="avatarHtml(1.25, editSettings)" class="pixel-art idle"></div>
              <div class="avatar-preview-copy">自分だけのピクセルキャラクター</div>
            </div>
            <div class="field">
              <label>性別</label>
              <div class="segmented">
                <button
                  v-for="option in genderOptions"
                  :key="option.value"
                  type="button"
                  class="seg-btn"
                  :class="{ active: editSettings.gender === option.value }"
                  @click="editSettings.gender = option.value"
                >{{ option.label }}</button>
              </div>
            </div>
            <div class="field">
              <label>髪型</label>
              <div class="segmented">
                <button
                  v-for="option in hairStyleOptions"
                  :key="option.value"
                  type="button"
                  class="seg-btn"
                  :class="{ active: editSettings.hair_style === option.value }"
                  @click="editSettings.hair_style = option.value"
                >{{ option.label }}</button>
              </div>
            </div>
            <div class="field">
              <label>服装</label>
              <div class="segmented">
                <button
                  v-for="option in outfitOptions"
                  :key="option.value"
                  type="button"
                  class="seg-btn"
                  :class="{ active: editSettings.outfit === option.value }"
                  @click="editSettings.outfit = option.value"
                >{{ option.label }}</button>
              </div>
            </div>
            <div class="field">
              <label>髪色</label>
              <div class="color-grid">
                <button
                  v-for="option in hairColorOptions"
                  :key="option.value"
                  type="button"
                  class="color-btn"
                  :class="{ active: editSettings.hair_color === option.value }"
                  :style="{ background: option.color }"
                  :title="option.label"
                  @click="editSettings.hair_color = option.value"
                ></button>
              </div>
            </div>
            <div class="field">
              <label>服の色</label>
              <div class="color-grid">
                <button
                  v-for="option in outfitColorOptions"
                  :key="option.value"
                  type="button"
                  class="color-btn"
                  :class="{ active: editSettings.outfit_color === option.value }"
                  :style="{ background: option.color }"
                  :title="option.label"
                  @click="editSettings.outfit_color = option.value"
                ></button>
              </div>
            </div>
          </div>
          <div class="field">
            <label>アクセサリー</label>
            <div class="segmented">
              <button
                v-for="option in accessoryOptions"
                :key="option.value"
                type="button"
                class="seg-btn"
                :class="{ active: editSettings.accessory === option.value }"
                @click="editSettings.accessory = option.value"
              >{{ option.label }}</button>
            </div>
          </div>
          <div class="field">
            <label>名前</label>
            <input v-model="editSettings.name" class="field-input" placeholder="ユイ" />
          </div>
          <div class="field">
            <label>性格・口調</label>
            <textarea v-model="editSettings.personality" class="field-textarea" rows="3"
              placeholder="明るく元気で投稿のお手伝いが大好き..." />
          </div>
          <div class="field">
            <label>朝の挨拶（5〜12時）</label>
            <input v-model="editSettings.greeting_morning" class="field-input" />
          </div>
          <div class="field">
            <label>昼の挨拶（12〜18時）</label>
            <input v-model="editSettings.greeting_afternoon" class="field-input" />
          </div>
          <div class="field">
            <label>夜の挨拶（18時〜）</label>
            <input v-model="editSettings.greeting_evening" class="field-input" />
          </div>
        </div>
        <div class="modal-footer">
          <button @click="saveSettings" class="save-btn" :disabled="saving">
            {{ saving ? '保存中...' : '保存する' }}
          </button>
        </div>
      </div>
    </div>
  </Transition>
</template>

<script setup lang="ts">
import { ref, reactive, watch, onMounted, onUnmounted, nextTick } from 'vue'

const props = withDefaults(defineProps<{ startHidden?: boolean }>(), { startHidden: false })
const widgetVisible = ref(!props.startHidden)

interface CharSettings {
  name: string
  avatar: string
  avatar_type: string
  gender: 'female' | 'male' | 'neutral'
  hair_style: 'short' | 'bob' | 'long' | 'spiky'
  hair_color: 'brown' | 'black' | 'gray' | 'blonde' | 'green' | 'purple'
  outfit: 'hoodie' | 'apron' | 'dress' | 'jacket'
  outfit_color: 'rose' | 'orange' | 'pink' | 'green' | 'blue' | 'purple'
  skin_tone: 'light' | 'tan' | 'brown' | 'dark'
  eye_color: 'brown' | 'blue' | 'green' | 'gray'
  accessory: 'none' | 'scarf' | 'glasses' | 'necklace' | 'belt'
  personality: string
  greeting_morning: string
  greeting_afternoon: string
  greeting_evening: string
}

const defaultSettings: CharSettings = {
  name: 'ユイ',
  avatar: '/avatars/f_hoodie.png',
  avatar_type: 'preset',
  gender: 'neutral',
  hair_style: 'bob',
  hair_color: 'brown',
  outfit: 'hoodie',
  outfit_color: 'rose',
  skin_tone: 'light',
  eye_color: 'brown',
  accessory: 'scarf',
  personality: '明るく元気で、投稿のお手伝いが大好きなAIアシスタントです。',
  greeting_morning: 'おはよう！今日も一緒に頑張ろうね✨',
  greeting_afternoon: 'こんにちは！投稿のお手伝いをするよ〜！',
  greeting_evening: '今日もお疲れ様！夜の投稿もバッチリだよ🌙',
}

const emojiPresets = ['🐱', '🐶', '🦊', '🐰', '🐼', '🦄', '🌸', '⭐', '🤖', '👾']
const quickReplies = ['今日の投稿を考えて', 'ハッシュタグを提案して', '投稿文を添削して']
const genderOptions = [
  { value: 'female' as const, label: '女性' },
  { value: 'male' as const, label: '男性' },
]
const hairStyleOptions = [
  { value: 'short' as const, label: 'ショート' },
  { value: 'bob' as const, label: 'ボブ' },
  { value: 'long' as const, label: 'ロング' },
  { value: 'spiky' as const, label: 'スパイキー' },
]
const outfitOptions = [
  { value: 'hoodie' as const, label: 'パーカー' },
  { value: 'apron' as const, label: 'エプロン' },
  { value: 'dress' as const, label: 'ワンピース' },
  { value: 'jacket' as const, label: 'ジャケット' },
]
const accessoryOptions = [
  { value: 'none' as const, label: 'なし' },
  { value: 'scarf' as const, label: 'マフラー' },
  { value: 'glasses' as const, label: 'メガネ' },
  { value: 'necklace' as const, label: '首飾り' },
  { value: 'belt' as const, label: 'ベルト' },
]
const hairColorOptions = [
  { value: 'brown' as const, label: 'ブラウン', color: '#5c3317' },
  { value: 'black' as const, label: 'ブラック', color: '#1f1f28' },
  { value: 'gray' as const, label: 'グレー', color: '#8790a0' },
  { value: 'blonde' as const, label: 'ブロンド', color: '#c79b35' },
  { value: 'green' as const, label: 'オリーブ', color: '#68751f' },
  { value: 'purple' as const, label: 'パープル', color: '#533d7a' },
]
const outfitColorOptions = [
  { value: 'rose' as const, label: 'ローズ', color: '#c85068' },
  { value: 'orange' as const, label: 'オレンジ', color: '#c06a24' },
  { value: 'pink' as const, label: 'ピンク', color: '#cf77a0' },
  { value: 'green' as const, label: 'グリーン', color: '#4b7f45' },
  { value: 'blue' as const, label: 'ブルー', color: '#3876a8' },
  { value: 'purple' as const, label: 'パープル', color: '#7e4fa0' },
]

// ──────────────────────────────────────────────────────
// LPC スプライト合成
// ──────────────────────────────────────────────────────
const SPRITE_BASE = '/sprites'

const PRESET_AVATARS = [
  { id: 'f_hoodie',   label: 'パーカー',     src: '/avatars/f_hoodie.png' },
  { id: 'f_dress',    label: 'ドレス',       src: '/avatars/f_dress.png' },
  { id: 'f_apron',    label: 'エプロン',     src: '/avatars/f_apron.png' },
  { id: 'f_skirt',    label: 'スカート',     src: '/avatars/f_skirt.png' },
  { id: 'm_jacket',   label: 'ジャケット',   src: '/avatars/m_jacket.png' },
  { id: 'm_hoodie',   label: 'パーカー',     src: '/avatars/m_hoodie.png' },
  { id: 'm_sweater',  label: 'セーター',     src: '/avatars/m_sweater.png' },
  { id: 'm_overalls', label: 'オーバーオール', src: '/avatars/m_overalls.png' },
]

const HAIR_FILTERS: Record<string, string> = {
  brown:  'none',
  black:  'brightness(0.25) saturate(0.5)',
  gray:   'brightness(0.9) saturate(0)',
  blonde: 'brightness(1.7) saturate(1.1) hue-rotate(12deg)',
  red:    'hue-rotate(-25deg) saturate(2)',
  purple: 'hue-rotate(280deg) saturate(1.6)',
  blue:   'hue-rotate(185deg) saturate(1.8)',
  green:  'hue-rotate(100deg) saturate(1.5)',
}

const OUTFIT_COLOR_FILE: Record<string, string> = {
  rose: 'red', orange: 'brown', pink: 'red',
  green: 'green', blue: 'blue', purple: 'purple',
  yellow: 'yellow', charcoal: 'black', red: 'red', brown: 'brown',
}

const SKIN_TONE_FILE: Record<string, string> = {
  light: 'light', tan: 'tanned2', brown: 'dark2', dark: 'darkelf2', warm: 'tanned2',
}

const TORSO_DIR: Record<string, string> = {
  hoodie: 'hoodie_f', apron: 'apron_f', dress: 'dress_f', jacket: 'jacket_f',
}
const TORSO_DIR_M: Record<string, string> = {
  hoodie: 'hoodie_m', apron: 'apron_m', dress: 'shirt_m', jacket: 'jacket_m',
}

async function loadImg(src: string): Promise<HTMLImageElement> {
  return new Promise((resolve, reject) => {
    const img = new Image()
    img.onload = () => resolve(img)
    img.onerror = () => reject(new Error(src))
    img.src = src
  })
}

async function compositeSprite(source: CharSettings): Promise<string> {
  const SZ = 64
  const SC = 3
  const canvas = document.createElement('canvas')
  canvas.width = SZ * SC
  canvas.height = SZ * SC
  const ctx = canvas.getContext('2d')!
  ctx.imageSmoothingEnabled = false
  const isMale = source.gender === 'male'
  const gKey   = isMale ? 'm' : 'f'
  const gender = isMale ? 'male' : 'female'
  const oColor = OUTFIT_COLOR_FILE[source.outfit_color as string] || 'blue'
  const hairStyle  = source.hair_style || 'long'
  const hairFilter = HAIR_FILTERS[source.hair_color as string] || 'none'
  const skinFile   = SKIN_TONE_FILE[source.skin_tone as string] || 'light'
  const outfit     = (source.outfit as string) || 'hoodie'
  const isDress    = outfit === 'dress'
  const torsoDir   = isMale ? (TORSO_DIR_M[outfit] || 'shirt_m') : (TORSO_DIR[outfit] || 'tunic_f')
  const accessory  = (source.accessory as string) || 'none'
  const eyeColor   = (source.eye_color as string) || 'brown'
  const layers: { src: string; filter?: string }[] = [
    { src: `${SPRITE_BASE}/skin/${gender}_${skinFile}.png` },
    { src: `${SPRITE_BASE}/face/${eyeColor}.png` },
    ...(!isDress ? [{ src: `${SPRITE_BASE}/legs/pants_${gKey}/${oColor}.png` }] : []),
    { src: `${SPRITE_BASE}/torso/${torsoDir}/${oColor}.png` },
    ...(accessory !== 'none' ? [{ src: `${SPRITE_BASE}/accessories/${accessory}.png` }] : []),
    { src: `${SPRITE_BASE}/hair/${hairStyle}.png`, filter: hairFilter },
  ]
  for (const layer of layers) {
    try {
      const img = await loadImg(layer.src)
      ctx.filter = (layer.filter && layer.filter !== 'none') ? layer.filter : 'none'
      ctx.drawImage(img, 0, SZ * 2, SZ, SZ, 0, 0, SZ * SC, SZ * SC)
    } catch { /* skip missing layer */ }
  }
  ctx.filter = 'none'
  return canvas.toDataURL('image/png')
}

// ──────────────────────────────────────────────────────
// State (must be declared before watch calls)
// ──────────────────────────────────────────────────────
const settings = reactive<CharSettings>({ ...defaultSettings })
const editSettings = reactive<CharSettings>({ ...defaultSettings })

const charSpriteUrl = ref('')
const editSpriteUrl = ref('')
async function regen()     { charSpriteUrl.value = await compositeSprite(settings) }
async function regenEdit() { editSpriteUrl.value = await compositeSprite(editSettings) }
watch(() => ({ ...settings }),     () => { if (settings.avatar_type === 'pixel') regen() })
watch(() => ({ ...editSettings }), () => { if (editSettings.avatar_type === 'pixel') regenEdit() })


function avatarHtml(scale = 1, source: CharSettings = settings): string {
  if (source.avatar_type === 'emoji') {
    const px = Math.round(40 * scale)
    return `<span style="font-size:${px}px;line-height:1;">${source.avatar}</span>`
  }
  if (source.avatar_type === 'image') {
    const px = Math.round(56 * scale)
    return `<img src="${source.avatar}" style="width:${px}px;height:${px}px;object-fit:contain;border-radius:50%;" />`
  }
  if (source.avatar_type === 'preset') {
    const h = Math.round(110 * scale)
    return `<img src="${source.avatar}" style="height:${h}px;width:auto;image-rendering:pixelated;image-rendering:crisp-edges;" />`
  }
  const url = source === editSettings ? editSpriteUrl.value : charSpriteUrl.value
  const sz = Math.round(48 * scale)
  if (!url) return `<div style="width:${sz}px;height:${sz}px;background:rgba(0,0,0,0.05);border-radius:4px;"></div>`
  return `<img src="${url}" style="width:${sz}px;height:${sz}px;image-rendering:pixelated;image-rendering:crisp-edges;" />`
}

const chatOpen = ref(false)
const bubble = ref('')
const messages = ref<{ role: string; content: string }[]>([])
const inputText = ref('')
const loading = ref(false)
const messagesEl = ref<HTMLElement | null>(null)
const settingsOpen = ref(false)
const saving = ref(false)

let bubbleTimer: number | null = null

function getGreeting() {
  const h = new Date().getHours()
  if (h >= 5 && h < 12) return settings.greeting_morning
  if (h >= 12 && h < 18) return settings.greeting_afternoon
  return settings.greeting_evening
}

function openChat() {
  widgetVisible.value = true
  chatOpen.value = true
  bubble.value = ''
}

function showBubble() {
  bubble.value = getGreeting()
  setTimeout(() => { bubble.value = '' }, 6000)
}

async function sendMessage() {
  const text = inputText.value.trim()
  if (!text || loading.value) return
  inputText.value = ''
  messages.value.push({ role: 'user', content: text })
  loading.value = true
  await nextTick()
  scrollToBottom()
  try {
    const res = await fetch('/api/character/chat', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ message: text, history: messages.value.slice(-10) }),
    })
    const data = await res.json()
    messages.value.push({ role: 'assistant', content: data.reply })
  } catch {
    messages.value.push({ role: 'assistant', content: 'ごめんなさい、うまく答えられませんでした😢' })
  } finally {
    loading.value = false
    await nextTick()
    scrollToBottom()
  }
}

function quickSend(text: string) {
  inputText.value = text
  sendMessage()
}

function scrollToBottom() {
  if (messagesEl.value) messagesEl.value.scrollTop = messagesEl.value.scrollHeight
}

function selectEmoji(e: string) {
  editSettings.avatar = e
  editSettings.avatar_type = 'emoji'
}

async function handleAvatarUpload(event: Event) {
  const file = (event.target as HTMLInputElement).files?.[0]
  if (!file) return
  const form = new FormData()
  form.append('image', file)
  const res = await fetch('/api/character/avatar', { method: 'POST', body: form })
  const data = await res.json()
  if (data.success) {
    editSettings.avatar = data.url
    editSettings.avatar_type = 'image'
  }
}

async function loadSettings() {
  try {
    const res = await fetch('/api/character/settings')
    const data = await res.json()
    Object.assign(settings, data)
    Object.assign(editSettings, data)
  } catch {}
}

async function saveSettings() {
  saving.value = true
  try {
    editSettings.avatar_type = editSettings.avatar_type || 'pixel'
    if (editSettings.avatar_type === 'pixel') editSettings.avatar = 'pixel'
    await fetch('/api/character/settings', {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(editSettings),
    })
    Object.assign(settings, editSettings)
    localStorage.setItem('uword-pixel-avatar-customized', '1')
    settingsOpen.value = false
  } finally {
    saving.value = false
  }
}

async function handleAvatarUpdated(event: Event) {
  const detail = (event as CustomEvent<Partial<CharSettings>>).detail || {}
  Object.assign(settings, detail)
  Object.assign(editSettings, detail)
  if (settings.avatar_type === 'pixel') await regen()
}

function handleOpenCharacterChat() {
  messages.value = []
  widgetVisible.value = true
  chatOpen.value = true
  settingsOpen.value = false
  bubble.value = ''
}

onMounted(() => {
  loadSettings().then(() => { regen(); regenEdit() })
  showBubble()
  bubbleTimer = window.setInterval(showBubble, 60000)
  window.addEventListener('uword-avatar-updated', handleAvatarUpdated)
  window.addEventListener('uword-open-character-chat', handleOpenCharacterChat)
  if (!localStorage.getItem('uword-pixel-avatar-customized')) {
    window.setTimeout(() => { settingsOpen.value = true }, 900)
  }
})
onUnmounted(() => {
  if (bubbleTimer) clearInterval(bubbleTimer)
  window.removeEventListener('uword-avatar-updated', handleAvatarUpdated)
  window.removeEventListener('uword-open-character-chat', handleOpenCharacterChat)
})
</script>

<style scoped>
/* ── ウィジェット配置 ── */
.char-widget {
  position: fixed;
  top: 70px;
  right: 20px;
  z-index: 500;
  display: flex;
  flex-direction: column;
  align-items: flex-end;
}

/* ── キャラアイコン（折りたたみ時） ── */
.char-trigger {
  display: flex;
  flex-direction: row;
  align-items: flex-end;
  gap: 10px;
  cursor: pointer;
}

.char-icon {
  background: rgba(255,255,255,0.92);
  border: 2px solid rgba(155, 89, 182, 0.3);
  border-radius: 16px;
  padding: 10px;
  box-shadow: 0 4px 20px rgba(155, 89, 182, 0.2);
  backdrop-filter: blur(8px);
  transition: transform 0.2s, box-shadow 0.2s;
}
.char-icon:hover {
  transform: scale(1.05);
  box-shadow: 0 6px 24px rgba(155, 89, 182, 0.3);
}

/* ── ピクセルアート ── */
.pixel-art {
  image-rendering: pixelated;
  display: flex;
  align-items: center;
  justify-content: center;
}
.pixel-art.idle {
  animation: idle-bob 1.2s ease-in-out infinite;
}
.pixel-art-sm {
  image-rendering: pixelated;
  display: flex;
  align-items: center;
}
.pixel-art-xs {
  image-rendering: pixelated;
  display: flex;
  align-items: center;
  flex-shrink: 0;
}

@keyframes idle-bob {
  0%, 100% { transform: translateY(0px); }
  50%       { transform: translateY(-4px); }
}

/* ── 吹き出し ── */
.speech-bubble {
  background: white;
  border: 2px solid rgba(155, 89, 182, 0.25);
  border-radius: 14px 14px 4px 14px;
  padding: 10px 14px;
  font-size: 12px;
  font-weight: 600;
  color: #3d1a4a;
  max-width: 180px;
  line-height: 1.5;
  box-shadow: 0 4px 16px rgba(0,0,0,0.1);
  white-space: pre-wrap;
  word-break: break-word;
  cursor: pointer;
}

/* ── チャットウィンドウ ── */
.chat-window {
  width: 320px;
  height: 480px;
  background: white;
  border-radius: 20px;
  box-shadow: 0 8px 40px rgba(155, 89, 182, 0.2);
  display: flex;
  flex-direction: column;
  overflow: hidden;
  border: 1px solid rgba(155, 89, 182, 0.15);
}

.chat-header {
  background: linear-gradient(135deg, #9b59b6, #6c3483);
  padding: 12px 14px;
  display: flex;
  align-items: center;
  gap: 10px;
  flex-shrink: 0;
}
.char-name {
  flex: 1;
  font-weight: 700;
  font-size: 14px;
  color: white;
  letter-spacing: 0.5px;
}
.header-acts { display: flex; gap: 4px; }
.hbtn {
  background: rgba(255,255,255,0.15);
  border: none;
  color: white;
  border-radius: 8px;
  padding: 4px 7px;
  cursor: pointer;
  font-size: 13px;
  transition: background 0.15s;
}
.hbtn:hover { background: rgba(255,255,255,0.3); }

/* ── メッセージエリア ── */
.chat-msgs {
  flex: 1;
  overflow-y: auto;
  padding: 14px;
  display: flex;
  flex-direction: column;
  gap: 10px;
  background: #faf8fd;
}

.chat-welcome {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 12px;
  padding: 16px 0;
}
.welcome-text {
  font-size: 13px;
  color: #5a3575;
  text-align: center;
  line-height: 1.6;
  font-weight: 500;
}
.quick-btns {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  justify-content: center;
}
.quick-btn {
  background: white;
  border: 1px solid rgba(155, 89, 182, 0.3);
  border-radius: 20px;
  padding: 5px 12px;
  font-size: 11px;
  color: #7d3a9e;
  cursor: pointer;
  transition: all 0.15s;
}
.quick-btn:hover { background: #f3e8ff; border-color: #9b59b6; }

.msg {
  display: flex;
  align-items: flex-end;
  gap: 7px;
}
.msg-user { flex-direction: row-reverse; }

.msg-bubble {
  background: white;
  border-radius: 16px 16px 16px 4px;
  padding: 9px 12px;
  font-size: 13px;
  max-width: 220px;
  line-height: 1.55;
  white-space: pre-wrap;
  word-break: break-word;
  box-shadow: 0 1px 4px rgba(0,0,0,0.06);
  border: 1px solid rgba(155, 89, 182, 0.1);
}
.msg-user .msg-bubble {
  background: linear-gradient(135deg, #9b59b6, #6c3483);
  color: white;
  border-radius: 16px 16px 4px 16px;
  border: none;
  box-shadow: 0 2px 8px rgba(155, 89, 182, 0.3);
}

.typing span {
  animation: blink 1.2s infinite;
  opacity: 0;
  font-size: 10px;
}
.typing span:nth-child(2) { animation-delay: 0.2s; }
.typing span:nth-child(3) { animation-delay: 0.4s; }
@keyframes blink { 0%,80%,100%{opacity:0} 40%{opacity:1} }

/* ── 入力エリア ── */
.input-row {
  display: flex;
  gap: 8px;
  padding: 10px 12px;
  border-top: 1px solid rgba(155, 89, 182, 0.1);
  background: white;
  flex-shrink: 0;
}
.chat-input {
  flex: 1;
  border: 1.5px solid rgba(155, 89, 182, 0.25);
  border-radius: 20px;
  padding: 8px 14px;
  font-size: 13px;
  outline: none;
  font-family: inherit;
  background: #faf8fd;
  color: #3d1a4a;
}
.chat-input:focus { border-color: #9b59b6; background: white; }
.send-btn {
  background: linear-gradient(135deg, #9b59b6, #6c3483);
  color: white;
  border: none;
  border-radius: 50%;
  width: 36px;
  height: 36px;
  font-size: 14px;
  cursor: pointer;
  flex-shrink: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  box-shadow: 0 2px 8px rgba(155, 89, 182, 0.4);
}
.send-btn:disabled { opacity: 0.45; cursor: not-allowed; }

/* ── 設定モーダル ── */
.modal-overlay {
  position: fixed;
  inset: 0;
  background: rgba(0,0,0,0.45);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 1000;
  padding: 20px;
}
.settings-modal {
  background: white;
  border-radius: 20px;
  width: 100%;
  max-width: 460px;
  max-height: 85vh;
  display: flex;
  flex-direction: column;
  overflow: hidden;
  box-shadow: 0 20px 60px rgba(0,0,0,0.2);
}
.modal-header {
  background: linear-gradient(135deg, #9b59b6, #6c3483);
  color: white;
  padding: 14px 18px;
  display: flex;
  justify-content: space-between;
  align-items: center;
  font-weight: 700;
  font-size: 15px;
  flex-shrink: 0;
}
.modal-body {
  padding: 20px;
  overflow-y: auto;
  display: flex;
  flex-direction: column;
  gap: 16px;
}
.modal-footer {
  padding: 14px 20px;
  border-top: 1px solid #f0f0f0;
  display: flex;
  justify-content: flex-end;
  flex-shrink: 0;
}
.save-btn {
  background: linear-gradient(135deg, #9b59b6, #6c3483);
  color: white;
  border: none;
  border-radius: 20px;
  padding: 10px 28px;
  font-size: 14px;
  font-weight: 700;
  cursor: pointer;
  box-shadow: 0 2px 8px rgba(155, 89, 182, 0.3);
}
.save-btn:disabled { opacity: 0.6; cursor: not-allowed; }

.field label {
  display: block;
  font-size: 11px;
  font-weight: 700;
  color: #888;
  margin-bottom: 7px;
  text-transform: uppercase;
  letter-spacing: 0.5px;
}
.field-input, .field-textarea {
  width: 100%;
  border: 1.5px solid #e0e0e0;
  border-radius: 10px;
  padding: 9px 12px;
  font-size: 13px;
  font-family: inherit;
  outline: none;
  resize: vertical;
}
.field-input:focus, .field-textarea:focus { border-color: #9b59b6; }

.preset-grid {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 8px;
  margin-bottom: 12px;
}
.preset-btn {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 4px;
  background: #f8f5ff;
  border: 2px solid transparent;
  border-radius: 12px;
  padding: 8px 4px 6px;
  cursor: pointer;
  transition: all 0.15s;
}
.preset-btn:hover { background: #f0e8ff; border-color: #c9aef5; }
.preset-btn.active { border-color: #9b59b6; background: #f0e8ff; }
.preset-thumb {
  height: 72px;
  width: auto;
  image-rendering: pixelated;
  image-rendering: crisp-edges;
}
.preset-label {
  font-size: 10px;
  color: #666;
  text-align: center;
  line-height: 1.2;
}
.emoji-grid {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  margin-bottom: 10px;
}
.emoji-btn {
  font-size: 22px;
  background: #f5f5f5;
  border: 2px solid transparent;
  border-radius: 10px;
  padding: 4px 6px;
  cursor: pointer;
  transition: all 0.15s;
  line-height: 1;
}
.pixel-default-btn {
  font-size: unset;
  padding: 5px 7px;
  display: flex;
  align-items: center;
  justify-content: center;
}
.emoji-btn:hover { background: #f3e8ff; }
.emoji-btn.active { border-color: #9b59b6; background: #f3e8ff; }

.upload-label {
  display: inline-block;
  background: #f5f5f5;
  border: 1px dashed #ccc;
  border-radius: 10px;
  padding: 7px 14px;
  font-size: 12px;
  cursor: pointer;
}
.upload-label:hover { background: #f3e8ff; border-color: #9b59b6; }
.avatar-preview {
  display: block;
  width: 56px;
  height: 56px;
  object-fit: contain;
  border-radius: 50%;
  margin-top: 8px;
}

.avatar-customizer {
  background: #faf8fd;
  border: 1px solid rgba(155, 89, 182, 0.12);
  border-radius: 16px;
  padding: 14px;
  display: flex;
  flex-direction: column;
  gap: 14px;
}
.avatar-preview-panel {
  min-height: 132px;
  background:
    linear-gradient(45deg, rgba(155, 89, 182, 0.08) 25%, transparent 25%),
    linear-gradient(-45deg, rgba(231, 84, 128, 0.08) 25%, transparent 25%),
    #fff;
  background-size: 18px 18px;
  border: 1px solid rgba(155, 89, 182, 0.14);
  border-radius: 14px;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 8px;
}
.avatar-preview-copy {
  color: #7d3a9e;
  font-size: 11px;
  font-weight: 700;
}
.segmented {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 6px;
}
.seg-btn {
  border: 1.5px solid rgba(155, 89, 182, 0.2);
  background: #fff;
  color: #5a3575;
  border-radius: 10px;
  min-height: 34px;
  font-size: 12px;
  font-weight: 700;
  cursor: pointer;
}
.seg-btn:hover,
.seg-btn.active {
  border-color: #9b59b6;
  background: #f3e8ff;
}
.color-grid {
  display: grid;
  grid-template-columns: repeat(6, minmax(0, 1fr));
  gap: 7px;
}
.color-btn {
  height: 30px;
  border: 2px solid rgba(90, 53, 117, 0.14);
  border-radius: 10px;
  cursor: pointer;
  box-shadow: inset 0 0 0 2px rgba(255,255,255,0.32);
}
.color-btn.active {
  border-color: #9b59b6;
  box-shadow: 0 0 0 3px rgba(155, 89, 182, 0.16), inset 0 0 0 2px rgba(255,255,255,0.38);
}

/* ── アニメーション ── */
.bubble-enter-active, .bubble-leave-active { transition: opacity 0.3s, transform 0.3s; }
.bubble-enter-from, .bubble-leave-to { opacity: 0; transform: translateX(10px); }

.chat-expand-enter-active, .chat-expand-leave-active { transition: opacity 0.25s, transform 0.25s; }
.chat-expand-enter-from, .chat-expand-leave-to { opacity: 0; transform: translateY(-12px) scale(0.97); transform-origin: top right; }

.fade-enter-active, .fade-leave-active { transition: opacity 0.25s; }
.fade-enter-from, .fade-leave-to { opacity: 0; }
</style>
