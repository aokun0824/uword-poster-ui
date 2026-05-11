<template>
  <div class="page-wrapper">
    <!-- トースト通知 -->
    <transition name="toast">
      <div v-if="toastVisible" class="toast" :class="`toast-${toastType}`">
        {{ toastMsg }}
      </div>
    </transition>
    <!-- Top-level page tabs -->
    <div class="page-tabs">
      <button
        v-for="tab in pageTabs"
        :key="tab.key"
        class="page-tab"
        :class="{ active: pageTab === tab.key }"
        @click="pageTab = tab.key as PageTab"
      >
        {{ tab.label }}
      </button>
    </div>

    <!-- ============================================================ -->
    <!-- 投稿タブ -->
    <!-- ============================================================ -->
    <div v-show="pageTab === 'post'" class="layout">
      <!-- Left Column: Post Form -->
      <section class="card form-card">
        <h2 class="section-title">新規投稿</h2>

        <!-- Platform Grid -->
        <div class="platform-grid">
          <button
            v-for="p in allPlatforms"
            :key="p.value"
            class="platform-btn"
            :class="{ active: activePlatform === p.value }"
            @click="activePlatform = p.value"
          >
            <span class="plat-icon">{{ p.icon }}</span>
            <span class="plat-name">{{ p.name }}</span>
            <span v-if="p.has_poster" class="plat-poster-badge">投稿</span>
            <span v-if="!p.has_poster" class="gen-only-badge">生成のみ</span>
          </button>
        </div>

        <!-- AI コンテンツ生成 -->
        <div class="generate-section" v-show="pageTab === 'post'">
          <h3 class="generate-title">AI コンテンツ生成</h3>

          <!-- Step 1: ソース入力 -->
          <div class="gen-step">
            <div class="step-badge">① ソース</div>
            <div class="generate-row">
              <select v-model="sourceType" class="generate-select" @change="summaryText = ''">
                <option value="url">記事 / 動画URL</option>
                <option value="topic">トピックから</option>
              </select>
              <input
                v-model="generateSource"
                :placeholder="sourceType === 'url' ? 'https://... （YouTube・ブログ記事 対応）' : 'キーワードやテーマを入力'"
                class="generate-input"
                @input="summaryText = ''"
              />
              <button
                v-if="sourceType === 'url'"
                @click="summarizeUrl"
                :disabled="summarizing || !generateSource.trim()"
                class="btn-summarize"
              >
                {{ summarizing ? '解析中...' : '📄 要約する' }}
              </button>
            </div>
            <div v-if="summarizeError" class="generate-error">{{ summarizeError }}</div>
          </div>

          <!-- Step 1.5: 要約結果（URL モードで要約後に表示） -->
          <div v-if="summaryText && sourceType === 'url'" class="summary-block">
            <div class="summary-header">
              <span class="step-badge">📝 要約結果</span>
              <span class="summary-hint">編集してからブログ生成できます</span>
              <button @click="summaryText = ''" class="btn-clear-summary">クリア</button>
            </div>
            <textarea v-model="summaryText" class="summary-textarea" rows="5" />
          </div>

          <!-- Step 2: トーン選択 + 生成 -->
          <div class="tone-section">
            <label class="tone-label">② トーン選択</label>
            <div class="tone-chips">
              <button
                v-for="tone in tones"
                :key="tone.value"
                @click="selectedTone = tone.value"
                class="tone-chip"
                :class="{ 'tone-chip-active': selectedTone === tone.value }"
              >
                {{ tone.label }}
              </button>
            </div>
            <div class="custom-style-row">
              <input
                v-model="customStyle"
                placeholder="追加スタイル指示（例: 河口湖の地域ネタを入れる）"
                class="custom-style-input"
              />
            </div>
            <button
              @click="generateContent"
              :disabled="generating || !canGenerate"
              class="btn-generate"
            >
              {{ generating ? '生成中...' : '✨ ブログを生成' }}
            </button>
            <div v-if="generateError" class="generate-error">{{ generateError }}</div>
          </div>
        </div>

        <!-- Title (プラットフォームによって表示) -->
        <div v-if="currentPlatformConfig?.has_title" class="field">
          <label class="label">
            タイトル
            <span class="char-count">{{ title.length }} / 50</span>
          </label>
          <input
            v-model="title"
            class="input"
            type="text"
            maxlength="50"
            placeholder="タイトルを入力"
          />
        </div>

        <!-- Content -->
        <div class="field">
          <label class="label">
            本文
            <span class="char-hint">200文字以上推奨</span>
          </label>
          <textarea
            v-model="content"
            class="textarea"
            rows="10"
            placeholder="本文を入力してください..."
          ></textarea>
          <!-- 修正1: 文字数カウンタ -->
          <div class="char-counter" :class="{ 'over-limit': isOverLimit }">
            {{ content.length }} / {{ charLimit }}文字
            <span v-if="isOverLimit" class="over-msg"> ⚠️ 制限超過</span>
          </div>
        </div>

        <!-- 修正4: ハッシュタグ チップ式UI -->
        <div class="hashtag-section">
          <label class="label">ハッシュタグ</label>
          <div class="hashtag-chips">
            <span v-for="(tag, i) in hashtagList" :key="i" class="hashtag-chip-edit">
              #{{ tag }}
              <button @click="removeHashtag(i)" class="chip-remove">×</button>
            </span>
            <input
              v-model="hashtagInput"
              @keydown.enter.prevent="addHashtag"
              @keydown.exact.prevent.comma="addHashtag"
              placeholder="タグを入力してEnter"
              class="hashtag-text-input"
            />
          </div>
          <div class="hashtag-hint">Enter またはカンマで追加</div>
        </div>

        <!-- AI 画像生成 -->
        <div v-if="['instagram','facebook'].includes(activePlatform)" class="image-gen-section">
          <div class="image-gen-header" @click="showImageGen = !showImageGen">
            <span class="image-gen-title">🎨 AI 画像生成 <span class="powered-by">powered by Gemini</span></span>
            <span class="image-gen-toggle">{{ showImageGen ? '▲' : '▼' }}</span>
          </div>
          <div v-if="showImageGen" class="image-gen-body">
            <div class="image-prompt-row">
              <textarea
                v-model="imagePrompt"
                placeholder="画像の説明を入力（空白にするとAIが内容から自動生成）"
                class="image-prompt-textarea"
                rows="2"
              />
            </div>
            <div class="image-gen-buttons">
              <button
                @click="generateImage"
                :disabled="generatingImage"
                class="btn-gen-image"
              >
                {{ generatingImage ? '⏳ 生成中...' : '✨ 画像を生成' }}
              </button>
              <span v-if="generatingImage" class="image-gen-hint">Geminiが画像を生成中です（10〜30秒）</span>
            </div>
            <div v-if="imageGenError" class="generate-error">{{ imageGenError }}</div>
            <div v-if="generatedImageUrl" class="generated-image-preview">
              <img :src="generatedImageUrl" alt="AI生成画像" class="gen-image-thumb generated-preview" />
              <div class="gen-image-meta">
                <div class="used-prompt-text">{{ usedImagePrompt }}</div>
                <div class="gen-image-actions">
                  <button @click="useGeneratedImage" class="btn-use-image">
                    📎 この画像を使う
                  </button>
                  <button @click="generateImage" :disabled="generatingImage" class="btn-regen-image">
                    🔄 再生成
                  </button>
                </div>
              </div>
            </div>
          </div>
        </div>

        <!-- 画像アップロード -->
        <div v-if="activePlatform !== 'uword' && activePlatform !== 'x_twitter' && activePlatform !== 'linkedin'" class="field image-section">
          <label class="label">投稿画像（任意）</label>
          <div class="image-upload-row">
            <label class="btn-file-label">
              ファイルを選択
              <input type="file" accept="image/*" @change="onImageSelect" class="file-input-hidden" />
            </label>
            <span v-if="imageFile" class="image-filename">{{ imageFile.name }}</span>
            <span v-else class="image-placeholder">画像未選択</span>
            <button v-if="imageFile" @click="imageFile = null" class="btn-clear-image">✕</button>
          </div>
        </div>

        <!-- Submit: 投稿対応プラットフォームはプレビュー→投稿、それ以外はコピー -->
        <div class="submit-area">
          <button
            v-if="currentPlatformConfig?.has_poster"
            class="btn-submit"
            :disabled="loading || !content.trim()"
            @click="openPreview"
          >
            <span v-if="loading" class="spinner"></span>
            <span v-else>投稿する</span>
          </button>
          <button
            v-else
            class="btn-copy-content"
            :disabled="!content.trim()"
            @click="copyContentToClipboard"
          >
            {{ copied ? '✅ コピーしました！' : '📋 クリップボードにコピー' }}
          </button>
        </div>

        <!-- 修正5: 成功後に投稿URLを表示 -->
        <div v-if="result" class="result" :class="result.success ? 'result-success' : 'result-error'">
          <span v-if="result.success">
            ✅ 投稿完了！
            <a v-if="result.post_url" :href="result.post_url" target="_blank" rel="noopener" class="post-link">
              投稿を確認する →
            </a>
          </span>
          <span v-else>エラー: {{ result.error }}</span>
        </div>

        <!-- 失敗時のアクションボタン -->
        <div v-if="result && !result.success" class="retry-actions">
          <button @click="retryPost" :disabled="loading" class="btn-retry">
            リトライ
          </button>
          <button @click="repairPost" :disabled="loading || repairing" class="btn-repair">
            {{ repairing ? '修復中...' : 'Playwright 修復' }}
          </button>
        </div>

        <!-- 修復ログ表示 -->
        <div v-if="repairLogs.length > 0" class="repair-log">
          <h4>修復ログ</h4>
          <div class="log-entries">
            <div v-for="(log, i) in repairLogs" :key="i" class="log-entry">{{ log }}</div>
          </div>
        </div>

        <!-- 定型文・URL 設定 -->
        <details class="boilerplate-panel">
          <summary class="boilerplate-summary">⚙️ 定型文・URL 設定</summary>
          <div class="bp-form">
            <div class="field">
              <label class="label">リアルタイム速報 末尾文</label>
              <textarea v-model="bp.uword_footer" class="textarea" rows="2" placeholder="リアルタイム速報に必ず付ける末尾文" />
            </div>
            <div class="field">
              <label class="label">ミニブログ 末尾文</label>
              <textarea v-model="bp.umatching_footer" class="textarea" rows="2" placeholder="ミニブログに必ず付ける末尾文" />
            </div>
            <div class="field">
              <label class="label">必ず含めるURL</label>
              <input v-model="bp.fixed_url" class="input" type="url" placeholder="https://..." />
            </div>
            <div class="field">
              <label class="label">必ず付けるハッシュタグ（カンマ区切り）</label>
              <input v-model="bpHashtagsStr" class="input" placeholder="例: AI,経営,自動化" />
            </div>
            <button @click="saveBoilerplate" class="btn-save-bp">保存</button>
            <span v-if="bpSaved" class="bp-saved">保存しました</span>
          </div>
        </details>
      </section>

      <!-- Right Column: Logs -->
      <section class="card logs-card">
        <div class="today-status-card">
          <div class="today-status-header">
            <h2 class="section-title">今日の投稿状況</h2>
            <button class="btn-refresh" @click="fetchTodayPostStatus" :disabled="todayStatusLoading">
              {{ todayStatusLoading ? '読込中...' : '更新' }}
            </button>
          </div>
          <div class="today-status-list">
            <div
              v-for="item in todayPostStatuses"
              :key="item.platform"
              class="today-status-badge"
              :class="{ complete: item.count >= DAILY_POST_TARGET }"
            >
              {{ item.label }}: {{ item.count }}/{{ DAILY_POST_TARGET }}本{{ item.count >= DAILY_POST_TARGET ? '完了 ✅' : '' }}
            </div>
          </div>
        </div>

        <div class="logs-header">
          <h2 class="section-title">直近ログ</h2>
          <button class="btn-refresh" @click="fetchLogs" :disabled="logsLoading">
            {{ logsLoading ? '読込中...' : '更新' }}
          </button>
        </div>

        <div v-if="logs.length === 0 && !logsLoading" class="logs-empty">
          ログがありません
        </div>

        <ul class="logs-list">
          <li v-for="(log, i) in logs" :key="i" class="log-item">
            <div class="log-top">
              <span class="badge" :class="log.status === 'success' ? 'badge-success' : 'badge-error'">
                {{ log.status === 'success' ? '成功' : '失敗' }}
              </span>
              <span class="log-platform">{{ log.platform }}</span>
              <span class="log-date">{{ formatDate(log.posted_at) }}</span>
            </div>
            <div v-if="log.title" class="log-title">{{ log.title }}</div>
            <div class="log-content">{{ log.content }}</div>
            <div v-if="log.error || log.error_message" class="log-error">{{ log.error || log.error_message }}</div>
          </li>
        </ul>
      </section>
    </div>

    <!-- ============================================================ -->
    <!-- 修正2: 投稿プレビューモーダル -->
    <!-- ============================================================ -->
    <div v-if="showPreview" class="preview-overlay" @click.self="showPreview = false">
      <div class="preview-modal">
        <div class="preview-header">
          <h3>📋 投稿プレビュー</h3>
          <button @click="showPreview = false" class="btn-close">×</button>
        </div>
        <div class="preview-platform">
          <span class="platform-badge">{{ currentPlatformConfig?.name || activePlatform }}</span>
        </div>
        <div v-if="previewData.title" class="preview-title">{{ previewData.title }}</div>
        <div class="preview-body">{{ previewData.fullContent }}</div>
        <div v-if="previewData.hashtagList.length > 0" class="preview-hashtags">
          <span v-for="tag in previewData.hashtagList" :key="tag" class="hashtag-chip">#{{ tag }}</span>
        </div>
        <div class="preview-char-count" :class="{ 'over-limit': previewData.fullContent.length > charLimit }">
          {{ previewData.fullContent.length }}文字
        </div>
        <div class="preview-actions">
          <button @click="showPreview = false" class="btn-cancel-preview">修正する</button>
          <button @click="confirmPost" :disabled="loading || isOverLimit" class="btn-confirm-post">
            {{ loading ? '投稿中...' : '✅ この内容で投稿する' }}
          </button>
        </div>
      </div>
    </div>

    <!-- ============================================================ -->
    <!-- 自動設定タブ -->
    <!-- ============================================================ -->
    <div v-if="pageTab === 'auto'" class="auto-settings">

      <!-- スケジュール設定セクション -->
      <section class="settings-section">
        <h3>📅 自動投稿スケジュール</h3>
        <div v-for="(sched, si) in autoSettings.schedules" :key="si" class="schedule-card">
          <div class="schedule-header">
            <select v-model="sched.platform">
              <option value="uword">リアルタイム速報</option>
              <option value="umatching">ミニブログ</option>
            </select>
            <label class="toggle">
              <input type="checkbox" v-model="sched.enabled" />
              <span>{{ sched.enabled ? '有効' : '無効' }}</span>
            </label>
            <button @click="autoSettings.schedules.splice(si, 1)" class="btn-remove">削除</button>
          </div>
          <!-- 曜日選択 -->
          <div class="day-selector">
            <label v-for="d in dayOptions" :key="d.value">
              <input type="checkbox" :value="d.value" v-model="sched.days" />
              {{ d.label }}
            </label>
          </div>
          <!-- 時刻追加 -->
          <div class="time-entries">
            <div v-for="(_t, ti) in sched.times" :key="ti" class="time-row">
              <input type="time" v-model="sched.times[ti]" class="time-input" />
              <button @click="sched.times.splice(ti, 1)" class="btn-small">×</button>
            </div>
            <button @click="sched.times.push('08:30')" class="btn-add-time">+ 時刻追加</button>
          </div>
        </div>
        <button @click="addSchedule" class="btn-add">+ スケジュール追加</button>
      </section>

      <!-- 記事生成ソース設定セクション -->
      <section class="settings-section">
        <h3>🤖 自動記事生成ソース設定</h3>
        <div v-for="(gen, gi) in autoSettings.generation" :key="gi" class="gen-card">
          <div class="gen-header">
            <select v-model="gen.platform">
              <option value="uword">リアルタイム速報用</option>
              <option value="umatching">ミニブログ用</option>
            </select>
            <button @click="autoSettings.generation.splice(gi, 1)" class="btn-remove">削除</button>
          </div>
          <!-- スタイル指示 -->
          <div class="style-note">
            <label>追加スタイル指示（AI への指示）</label>
            <input v-model="gen.style_note" placeholder="例: 必ず体験談を入れる、河口湖地域の話題を絡める" />
          </div>
          <!-- ソース一覧 -->
          <div class="sources-list">
            <h4>参照ソース</h4>
            <div v-for="(src, si) in gen.sources" :key="si" class="source-row">
              <select v-model="src.type" class="src-type">
                <option value="url">URL</option>
                <option value="topic">トピック</option>
              </select>
              <input v-model="src.value" :placeholder="src.type === 'url' ? 'https://...' : 'キーワード、テーマ'" class="src-value" />
              <label><input type="checkbox" v-model="src.enabled" /> 有効</label>
              <button @click="gen.sources.splice(si, 1)" class="btn-small">×</button>
            </div>
            <button @click="gen.sources.push({type:'topic', value:'', enabled:true})" class="btn-add-time">+ ソース追加</button>
          </div>
        </div>
        <button @click="addGenConfig" class="btn-add">+ 生成設定追加</button>
      </section>

      <!-- アクション -->
      <div class="settings-actions">
        <button @click="saveAutoSettings" :disabled="savingSettings" class="btn-save-settings">
          {{ savingSettings ? '保存中...' : '💾 設定を保存' }}
        </button>
        <div class="test-run">
          <span>即時テスト実行:</span>
          <button @click="runNow('uword')" class="btn-run-now">▶ 速報を今すぐ生成・投稿</button>
          <button @click="runNow('umatching')" class="btn-run-now">▶ ミニブログを今すぐ生成・投稿</button>
        </div>
      </div>

      <!-- 次回実行スケジュール表示 -->
      <section class="settings-section">
        <h3>⏰ 登録済みジョブ</h3>
        <div v-if="scheduledJobs.length === 0" class="empty">スケジュール未設定</div>
        <div v-for="job in scheduledJobs" :key="job.id" class="job-row">
          <code>{{ job.id }}</code>
          <span>次回: {{ job.next_run }}</span>
        </div>
        <button @click="fetchJobs" class="btn-refresh-jobs">🔄 更新</button>
      </section>
    </div>

    <!-- ============================================================ -->
    <!-- 週次レビュータブ -->
    <!-- ============================================================ -->
    <div v-if="pageTab === 'review'" class="review-tab">
      <!-- サマリーカード -->
      <div class="review-summary">
        <div class="summary-card">
          <div class="sc-value">{{ review.summary?.total ?? '-' }}</div>
          <div class="sc-label">投稿数</div>
        </div>
        <div class="summary-card accent">
          <div class="sc-value">{{ review.summary?.avg_score?.toFixed(1) ?? '-' }}</div>
          <div class="sc-label">平均スコア</div>
        </div>
        <div class="summary-card green">
          <div class="sc-value">{{ review.summary?.high_score ?? '-' }}</div>
          <div class="sc-label">高評価(8+)</div>
        </div>
        <div class="summary-card red">
          <div class="sc-value">{{ review.summary?.needs_improvement ?? '-' }}</div>
          <div class="sc-label">要改善</div>
        </div>
      </div>
      <div class="review-actions">
        <button @click="fetchReview" class="btn-refresh">🔄 更新</button>
        <button @click="runReview" :disabled="runningReview" class="btn-run-now">
          {{ runningReview ? '生成中...' : '▶ 今すぐレビュー実行' }}
        </button>
        <span class="review-date" v-if="review.date">{{ review.date }}</span>
      </div>
      <!-- 投稿カード一覧 -->
      <div class="post-cards">
        <div v-for="post in review.posts" :key="post.title" class="post-card">
          <div class="post-card-header">
            <span class="score-badge" :class="scoreColor(post.score)">{{ post.score ?? 'N/A' }}/10</span>
            <span class="platform-badge">{{ post.platform }}</span>
            <span class="post-title">{{ post.title }}</span>
          </div>
          <div class="post-meta">{{ post.posted_at }}</div>
          <div class="post-content-preview">{{ post.content }}</div>
          <details class="ai-eval">
            <summary>AI評価詳細</summary>
            <table class="eval-table">
              <tbody>
                <tr><td>フック</td><td>{{ post.hook_strength }}</td></tr>
                <tr><td>CTA</td><td>{{ post.cta_present ? 'あり' : 'なし' }}</td></tr>
                <tr><td>ターゲット一致</td><td>{{ post.target_match }}</td></tr>
                <tr><td>禁止語</td><td :class="post.forbidden_words && post.forbidden_words !== 'なし' ? 'warn-text' : ''">{{ post.forbidden_words || 'なし' }}</td></tr>
                <tr><td>改善提案</td><td>{{ post.improvement }}</td></tr>
              </tbody>
            </table>
          </details>
        </div>
        <div v-if="!review.posts?.length" class="empty">レポートがありません。「今すぐレビュー実行」で生成してください。</div>
      </div>
    </div>

    <!-- ============================================================ -->
    <!-- 診断タブ -->
    <!-- ============================================================ -->
    <div v-if="pageTab === 'diagnose'" class="diagnose-tab">
      <h3>Playwright ページ診断</h3>
      <div class="diagnose-buttons">
        <button @click="diagnose('uword')" :disabled="diagnosing" class="btn-diagnose">
          🔍 リアルタイム速報を診断
        </button>
        <button @click="diagnose('umatching')" :disabled="diagnosing" class="btn-diagnose">
          🔍 ミニブログを診断
        </button>
      </div>
      <div v-if="diagnosing" class="diagnosing-msg">診断中... (Playwright起動中)</div>
      <div v-if="diagResult" class="diag-result">
        <div class="diag-header">
          <span :class="diagResult.ok ? 'status-ok' : 'status-error'">{{ diagResult.ok ? '✅ 正常' : '❌ 問題あり' }}</span>
          <span class="diag-platform">{{ diagResult.platform }}</span>
          <span class="diag-time">{{ diagResult.timestamp }}</span>
        </div>
        <div class="checks-list">
          <div v-for="check in diagResult.checks" :key="check.label" class="check-item">
            <span class="check-icon">{{ check.status === 'ok' ? '✅' : check.status === 'warn' ? '⚠️' : '❌' }}</span>
            <span class="check-label">{{ check.label }}</span>
            <span class="check-detail">{{ check.detail }}</span>
          </div>
        </div>
      </div>
    </div>

    <!-- ============================================================ -->
    <!-- ログ詳細タブ -->
    <!-- ============================================================ -->
    <div v-if="pageTab === 'logs'" class="logs-tab">
      <div class="logs-header">
        <h3>投稿ログ詳細</h3>
        <button @click="fetchDetailLogs" class="btn-refresh">🔄 更新</button>
      </div>
      <div class="logs-filter">
        <label>
          <input type="checkbox" v-model="showErrorsOnly" /> エラーのみ表示
        </label>
      </div>
      <div class="detail-logs">
        <div v-for="log in filteredLogs" :key="log.id"
             class="detail-log-item" :class="log.status === 'success' ? 'log-success' : 'log-error'">
          <div class="log-row-header">
            <span class="log-status-badge" :class="log.status">{{ log.status }}</span>
            <span class="log-platform">{{ log.platform }}</span>
            <span class="log-title">{{ log.title || '(タイトルなし)' }}</span>
            <span class="log-date">{{ log.posted_at?.slice(0,16) }}</span>
          </div>
          <div class="log-content-preview">{{ log.content }}</div>
          <div v-if="log.error" class="log-error-msg">⚠️ {{ log.error }}</div>
          <div v-if="log.retry_attempt > 0" class="log-retry">リトライ回数: {{ log.retry_attempt }}</div>
        </div>
        <div v-if="!filteredLogs.length" class="empty">ログがありません</div>
      </div>
    </div>

    <!-- ============================================================ -->
    <!-- 設定タブ -->
    <!-- ============================================================ -->
    <div v-if="pageTab === 'settings'" class="settings-tab">
      <section class="settings-section">
        <h3>🔑 ログイン情報（アカウント設定）</h3>
        <div class="creds-form">
          <!-- uword -->
          <div class="cred-accordion">
            <button class="cred-header" @click="toggleCred('uword')">
              <span>📰 リアルタイム速報</span>
              <span :class="hasCredential('uword') ? 'badge-ok' : 'badge-warn'">{{ hasCredential('uword') ? '✅ 設定済' : '⚠️ 未設定' }}</span>
              <span class="cred-arrow">{{ openCred === 'uword' ? '▲' : '▼' }}</span>
            </button>
            <div v-show="openCred === 'uword'" class="cred-body">
              <div class="creds-grid">
                <label>ユーザー名 / メール</label>
                <input v-model="creds.uword.username" type="text" placeholder="sakajungo@gmail.com" />
                <label>パスワード</label>
                <input v-model="creds.uword.password" type="password" placeholder="パスワード" />
                <label>サイトURL（ログインページ）</label>
                <input v-model="creds.uword.site_url" type="url" placeholder="https://u-word.com/horby/login" />
                <label>投稿URL</label>
                <input v-model="creds.uword.post_url" type="url" placeholder="https://u-word.com/horby/myPage/realTimePost" />
              </div>
            </div>
          </div>
          <!-- umatching -->
          <div class="cred-accordion">
            <button class="cred-header" @click="toggleCred('umatching')">
              <span>📝 ミニブログ</span>
              <span :class="hasCredential('umatching') ? 'badge-ok' : 'badge-warn'">{{ hasCredential('umatching') ? '✅ 設定済' : '⚠️ 未設定' }}</span>
              <span class="cred-arrow">{{ openCred === 'umatching' ? '▲' : '▼' }}</span>
            </button>
            <div v-show="openCred === 'umatching'" class="cred-body">
              <div class="creds-grid">
                <label>ユーザー名 / メール</label>
                <input v-model="creds.umatching.username" type="text" placeholder="your@email.com" />
                <label>パスワード</label>
                <input v-model="creds.umatching.password" type="password" placeholder="パスワード" />
                <label>サイトURL（ログインページ）</label>
                <input v-model="creds.umatching.site_url" type="url" placeholder="https://u-word.com/horby/login" />
                <label>投稿URL</label>
                <input v-model="creds.umatching.post_url" type="url" placeholder="https://u-word.com/horby/myPage/blogPost" />
              </div>
            </div>
          </div>
          <!-- facebook -->
          <div class="cred-accordion">
            <button class="cred-header" @click="toggleCred('facebook')">
              <span>🔵 Facebook</span>
              <span :class="hasCredential('facebook') ? 'badge-ok' : 'badge-warn'">{{ hasCredential('facebook') ? '✅ 設定済' : '⚠️ 未設定' }}</span>
              <span class="cred-arrow">{{ openCred === 'facebook' ? '▲' : '▼' }}</span>
            </button>
            <div v-show="openCred === 'facebook'" class="cred-body">
              <div class="creds-grid">
                <label>ユーザー名 / メール</label>
                <input v-model="creds.facebook.username" type="text" placeholder="your@email.com" />
                <label>パスワード</label>
                <input v-model="creds.facebook.password" type="password" placeholder="パスワード" />
              </div>
            </div>
          </div>
          <!-- instagram -->
          <div class="cred-accordion">
            <button class="cred-header" @click="toggleCred('instagram')">
              <span>📸 Instagram</span>
              <span :class="hasCredential('instagram') ? 'badge-ok' : 'badge-warn'">{{ hasCredential('instagram') ? '✅ 設定済' : '⚠️ 未設定' }}</span>
              <span class="cred-arrow">{{ openCred === 'instagram' ? '▲' : '▼' }}</span>
            </button>
            <div v-show="openCred === 'instagram'" class="cred-body">
              <div class="creds-grid">
                <label>ユーザー名 / メール</label>
                <input v-model="creds.instagram.username" type="text" placeholder="your@email.com" />
                <label>パスワード</label>
                <input v-model="creds.instagram.password" type="password" placeholder="パスワード" />
              </div>
            </div>
          </div>
          <!-- threads -->
          <div class="cred-accordion">
            <button class="cred-header" @click="toggleCred('threads')">
              <span>🧵 Threads</span>
              <span :class="hasCredential('threads') ? 'badge-ok' : 'badge-warn'">{{ hasCredential('threads') ? '✅ 設定済' : '⚠️ 未設定' }}</span>
              <span class="cred-arrow">{{ openCred === 'threads' ? '▲' : '▼' }}</span>
            </button>
            <div v-show="openCred === 'threads'" class="cred-body">
              <div class="creds-grid">
                <label>ユーザー名 / メール</label>
                <input v-model="creds.threads.username" type="text" placeholder="your@email.com" />
                <label>パスワード</label>
                <input v-model="creds.threads.password" type="password" placeholder="パスワード" />
              </div>
            </div>
          </div>
          <!-- note -->
          <div class="cred-accordion">
            <button class="cred-header" @click="toggleCred('note')">
              <span>📖 Note</span>
              <span :class="hasCredential('note') ? 'badge-ok' : 'badge-warn'">{{ hasCredential('note') ? '✅ 設定済' : '⚠️ 未設定' }}</span>
              <span class="cred-arrow">{{ openCred === 'note' ? '▲' : '▼' }}</span>
            </button>
            <div v-show="openCred === 'note'" class="cred-body">
              <div class="creds-grid">
                <label>ユーザー名 / メール</label>
                <input v-model="creds.note.username" type="text" placeholder="your@email.com" />
                <label>パスワード</label>
                <input v-model="creds.note.password" type="password" placeholder="パスワード" />
                <label>Cookie（任意）</label>
                <input v-model="creds.note.cookie" type="text" placeholder="note_session=..." />
              </div>
            </div>
          </div>
          <!-- x_twitter -->
          <div class="cred-accordion">
            <button class="cred-header" @click="toggleCred('x_twitter')">
              <span>✖️ X (Twitter)</span>
              <span :class="hasCredential('x_twitter') ? 'badge-ok' : 'badge-warn'">{{ hasCredential('x_twitter') ? '✅ 設定済' : '⚠️ 未設定' }}</span>
              <span class="cred-arrow">{{ openCred === 'x_twitter' ? '▲' : '▼' }}</span>
            </button>
            <div v-show="openCred === 'x_twitter'" class="cred-body">
              <div class="creds-grid">
                <label>ユーザー名 / メール</label>
                <input v-model="creds.x_twitter.username" type="text" placeholder="your@email.com" />
                <label>パスワード</label>
                <input v-model="creds.x_twitter.password" type="password" placeholder="パスワード" />
              </div>
            </div>
          </div>
          <!-- linkedin -->
          <div class="cred-accordion">
            <button class="cred-header" @click="toggleCred('linkedin')">
              <span>💼 LinkedIn</span>
              <span :class="hasCredential('linkedin') ? 'badge-ok' : 'badge-warn'">{{ hasCredential('linkedin') ? '✅ 設定済' : '⚠️ 未設定' }}</span>
              <span class="cred-arrow">{{ openCred === 'linkedin' ? '▲' : '▼' }}</span>
            </button>
            <div v-show="openCred === 'linkedin'" class="cred-body">
              <div class="creds-grid">
                <label>ユーザー名 / メール</label>
                <input v-model="creds.linkedin.username" type="text" placeholder="your@email.com" />
                <label>パスワード</label>
                <input v-model="creds.linkedin.password" type="password" placeholder="パスワード" />
              </div>
            </div>
          </div>

          <button @click="saveCreds" class="btn-save-creds">💾 保存（ブラウザに記憶）</button>
          <p class="creds-note">⚠️ パスワードはブラウザ localStorage にのみ保存。サーバーには送信時のみ使用。</p>
        </div>
      </section>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, watch } from 'vue'

const BASE = import.meta.env.VITE_API_BASE || ''

interface PostResult {
  success: boolean
  post_url: string
  error: string
}

interface LogEntry {
  id?: number
  config_id?: number
  platform: string
  status: string
  title: string | null
  content: string | null
  posted_at: string | null
  error: string | null
  error_message?: string | null
}

interface BoilerplateData {
  uword_footer: string
  umatching_footer: string
  fixed_url: string
  fixed_hashtags: string[]
}

interface ScheduleEntry {
  platform: 'uword' | 'umatching'
  days: string[]
  times: string[]
  enabled: boolean
}

interface GenerationConfig {
  platform: 'uword' | 'umatching'
  sources: { type: string; value: string; enabled: boolean }[]
  style_note: string
}

interface AutoSettingsData {
  generation: GenerationConfig[]
  schedules: ScheduleEntry[]
}

interface ReviewPost {
  platform: string
  title: string
  score: number | null
  posted_at: string
  content: string
  hook_strength: string
  cta_present: boolean
  target_match: string
  forbidden_words: string
  improvement: string
}

interface DiagResult {
  ok: boolean
  platform: string
  checks: { label: string; status: string; detail: string }[]
  timestamp: string
}

type PageTab = 'post' | 'auto' | 'review' | 'diagnose' | 'logs' | 'settings'

// クレデンシャル（localStorage に永続化）
function safeParseLocalStorage<T>(key: string, fallback: T): T {
  try {
    const raw = localStorage.getItem(key)
    return raw ? JSON.parse(raw) as T : fallback
  } catch {
    return fallback
  }
}

// _savedCreds removed: replaced by safeParseLocalStorage below
type PlatformCreds = {
  username: string
  password: string
  site_url?: string
  post_url?: string
  cookie?: string
}

const creds = ref<{
  uword: { username: string; password: string; site_url: string; post_url: string }
  umatching: { username: string; password: string; site_url: string; post_url: string }
  facebook: PlatformCreds
  instagram: PlatformCreds
  threads: PlatformCreds
  note: PlatformCreds
  x_twitter: PlatformCreds
  linkedin: PlatformCreds
}>({
  uword: { username: '', password: '', site_url: 'https://u-word.com/horby/login', post_url: 'https://u-word.com/horby/myPage/realTimePost' },
  umatching: { username: '', password: '', site_url: '', post_url: '' },
  facebook: { username: '', password: '' },
  instagram: { username: '', password: '' },
  threads: { username: '', password: '' },
  note: { username: '', password: '', cookie: '' },
  x_twitter: { username: '', password: '' },
  linkedin: { username: '', password: '' },
  ...(safeParseLocalStorage<Record<string, unknown>>('uword_creds', {})),
})

const openCred = ref<string | null>(null)

function toggleCred(platform: string) {
  openCred.value = openCred.value === platform ? null : platform
}

function hasCredential(platform: string): boolean {
  const c = creds.value[platform as keyof typeof creds.value]
  return !!(c && (c as { username?: string }).username)
}

function saveCreds() {
  localStorage.setItem('uword_creds', JSON.stringify(creds.value))
  showToast('クレデンシャルを保存しました', 'success')
}

const currentCreds = computed(() =>
  creds.value[activePlatform.value as keyof typeof creds.value] || creds.value.uword
)

// トースト通知
const toastMsg = ref('')
const toastType = ref<'success' | 'error' | 'info'>('info')
const toastVisible = ref(false)

function showToast(msg: string, type: 'success' | 'error' | 'info' = 'info') {
  toastMsg.value = msg
  toastType.value = type
  toastVisible.value = true
  setTimeout(() => { toastVisible.value = false }, 3000)
}

// ページタブ
const pageTabs = [
  { key: 'post', label: '✏️ 投稿' },
  { key: 'auto', label: '⚙️ 自動設定' },
  { key: 'review', label: '📊 週次レビュー' },
  { key: 'diagnose', label: '🔍 診断' },
  { key: 'logs', label: '📋 ログ詳細' },
  { key: 'settings', label: '⚙️ 設定' },
]
const pageTab = ref<PageTab>('post')

// フォーム状態
const activePlatform = ref('uword')
const activeTab = computed(() =>
  ['uword', 'umatching'].includes(activePlatform.value)
    ? (activePlatform.value as 'uword' | 'umatching')
    : 'uword'
)
const title = ref('')
const content = ref('')
const loading = ref(false)
const result = ref<PostResult | null>(null)
const imageFile = ref<File | null>(null)
const repairing = ref(false)
const repairLogs = ref<string[]>([])

// プラットフォーム一覧
const allPlatforms = ref<{value: string; name: string; icon: string; char_limit: number; has_poster: boolean; has_title: boolean}[]>([])

async function fetchPlatforms() {
  try {
    const res = await fetch(`${BASE}/api/platforms`)
    allPlatforms.value = await res.json()
  } catch {
    // fallback to defaults
    allPlatforms.value = [
      { value: 'uword',     name: 'リアルタイム速報', icon: '📰', char_limit: 400,   has_poster: true,  has_title: true  },
      { value: 'umatching', name: 'ミニブログ',       icon: '📝', char_limit: 300,   has_poster: true,  has_title: false },
      { value: 'facebook',  name: 'Facebook',         icon: '🔵', char_limit: 2000,  has_poster: false, has_title: false },
      { value: 'instagram', name: 'Instagram',        icon: '📸', char_limit: 2200,  has_poster: false, has_title: false },
      { value: 'threads',   name: 'Threads',          icon: '🧵', char_limit: 500,   has_poster: true,  has_title: false },
      { value: 'note',      name: 'Note',             icon: '📖', char_limit: 10000, has_poster: true,  has_title: true  },
      { value: 'x_twitter', name: 'X (Twitter)',      icon: '✖️',  char_limit: 280,   has_poster: true,  has_title: false },
      { value: 'linkedin',  name: 'LinkedIn',         icon: '💼', char_limit: 3000,  has_poster: true,  has_title: true  },
    ]
  }
}

const currentPlatformConfig = computed(() =>
  allPlatforms.value.find(p => p.value === activePlatform.value) ?? allPlatforms.value[0]
)

// コピー状態
const copied = ref(false)

// AI 画像生成
const showImageGen = ref(false)
const imagePrompt = ref('')
const generatingImage = ref(false)
const imageGenError = ref('')
const generatedImageUrl = ref('')
const generatedImagePath = ref('')
const usedImagePrompt = ref('')
const generatedImageBlob = ref<Blob | null>(null)

async function generateImage() {
  generatingImage.value = true
  imageGenError.value = ''
  try {
    const res = await fetch(`${BASE}/api/generate-image`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        content: content.value || title.value,
        custom_prompt: imagePrompt.value,
        platform: activePlatform.value,
      }),
    })
    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: res.statusText }))
      imageGenError.value = `画像生成失敗: ${err.detail || res.statusText}`
      return
    }
    const data = await res.json()
    if (data.image_url) {
      generatedImageUrl.value = data.image_url
      generatedImagePath.value = data.image_path || ''
      usedImagePrompt.value = data.used_prompt || imagePrompt.value
      generatedImageBlob.value = null
      showToast('画像を生成しました ✨', 'success')
      return
    }
    const mimeType = data.mime_type || 'image/png'
    generatedImageUrl.value = `data:${mimeType};base64,${data.image_data}`
    generatedImagePath.value = data.image_path || ''
    usedImagePrompt.value = data.used_prompt || ''
    // base64 → Blob（添付用）
    const bytes = atob(data.image_data)
    const arr = new Uint8Array(bytes.length)
    for (let i = 0; i < bytes.length; i++) arr[i] = bytes.charCodeAt(i)
    generatedImageBlob.value = new Blob([arr], { type: mimeType })
    showToast('画像を生成しました ✨', 'success')
  } catch {
    imageGenError.value = 'ネットワークエラー: バックエンドに接続できません'
    showToast('画像生成に失敗しました', 'error')
  } finally {
    generatingImage.value = false
  }
}

function useGeneratedImage() {
  if (!generatedImageBlob.value) return
  const ext = generatedImageBlob.value.type.includes('jpeg') ? 'jpg' : 'png'
  imageFile.value = new File([generatedImageBlob.value], `ai-generated.${ext}`, { type: generatedImageBlob.value.type })
  showToast('生成画像を添付しました', 'success')
  showImageGen.value = false
}

async function copyContentToClipboard() {
  const text = [
    title.value ? `${title.value}\n\n` : '',
    content.value,
    hashtagList.value.length ? '\n\n' + hashtagList.value.map(t => `#${t}`).join(' ') : ''
  ].join('')
  try {
    await navigator.clipboard.writeText(text)
    copied.value = true
    showToast('クリップボードにコピーしました', 'success')
    setTimeout(() => { copied.value = false }, 3000)
  } catch {
    showToast('コピーに失敗しました', 'error')
  }
}

// 文字数制限 computed
const charLimit = computed(() => currentPlatformConfig.value?.char_limit ?? 400)
const isOverLimit = computed(() => content.value.length > charLimit.value)

// 修正4: ハッシュタグ チップ式管理
const hashtagList = ref<string[]>([])
const hashtagInput = ref('')

function addHashtag() {
  const tag = hashtagInput.value.trim().replace(/^#/, '')
  if (tag && !hashtagList.value.includes(tag)) {
    hashtagList.value.push(tag)
  }
  hashtagInput.value = ''
}

function removeHashtag(i: number) {
  hashtagList.value.splice(i, 1)
}

// 修正2: プレビューモーダル
const showPreview = ref(false)
const previewData = ref({ title: '', fullContent: '', hashtags: '', hashtagList: [] as string[] })

async function openPreview() {
  let fullContent = content.value

  try {
    const bpRes = await fetch(`${BASE}/api/boilerplate`)
    const bpJson = await bpRes.json()
    const footer = activeTab.value === 'uword' ? bpJson.uword_footer : bpJson.umatching_footer
    if (footer) fullContent += '\n\n' + footer
    if (bpJson.fixed_url) fullContent += '\n' + bpJson.fixed_url

    const allHashtags = [
      ...hashtagList.value,
      ...(bpJson.fixed_hashtags || [])
    ]

    previewData.value = {
      title: title.value,
      fullContent,
      hashtags: allHashtags.join(', '),
      hashtagList: allHashtags
    }
  } catch {
    // ボイラープレート取得失敗時はそのままプレビュー
    previewData.value = {
      title: title.value,
      fullContent,
      hashtags: hashtagList.value.join(', '),
      hashtagList: [...hashtagList.value]
    }
  }

  showPreview.value = true
}

async function confirmPost() {
  showPreview.value = false
  await submitPost()
}

// AI 生成
const sourceType = ref<'url' | 'topic'>('topic')
const generateSource = ref('')
const generating = ref(false)
const generateError = ref('')

// URL 要約
const summarizing = ref(false)
const summaryText = ref('')
const summarizeError = ref('')

// 生成可能条件: URLモードは要約済み or トピックモードはテキストあり
const canGenerate = computed(() =>
  sourceType.value === 'url'
    ? summaryText.value.trim().length > 0
    : generateSource.value.trim().length > 0
)

// トーン設定
const selectedTone = ref(safeParseLocalStorage<string>('uword_tone', 'professional'))
const customStyle = ref(safeParseLocalStorage<string>('uword_custom_style', ''))
const tones = ref<{value: string; label: string}[]>([])

watch(selectedTone, (v) => localStorage.setItem('uword_tone', v))
watch(customStyle, (v) => localStorage.setItem('uword_custom_style', v))

async function fetchTones() {
  try {
    const res = await fetch(`${BASE}/api/tones`)
    tones.value = await res.json()
  } catch {
    // silent fail
  }
}

// ログ
const logs = ref<LogEntry[]>([])
const logsLoading = ref(false)
const DAILY_POST_TARGET = 2
const todayStatusLoading = ref(false)
const todayPostCounts = ref<Record<string, number>>({ uword: 0, umatching: 0 })
const todayPostStatuses = computed(() => [
  { platform: 'uword', label: '今日のリアルタイム速報', count: todayPostCounts.value.uword || 0 },
  { platform: 'umatching', label: '今日のミニブログ', count: todayPostCounts.value.umatching || 0 },
])

// 定型文
const bp = ref<BoilerplateData>({
  uword_footer: '',
  umatching_footer: '',
  fixed_url: '',
  fixed_hashtags: [],
})
const bpSaved = ref(false)

// 定型文ハッシュタグ: カンマ区切り文字列 ↔ 配列
const bpHashtagsStr = computed({
  get: () => bp.value.fixed_hashtags.join(', '),
  set: (v: string) => {
    bp.value.fixed_hashtags = v.split(',').map((h) => h.trim()).filter(Boolean)
  },
})

// 自動設定
const autoSettings = ref<AutoSettingsData>({ generation: [], schedules: [] })
const savingSettings = ref(false)
const scheduledJobs = ref<any[]>([])

const dayOptions = [
  { value: 'mon', label: '月' },
  { value: 'tue', label: '火' },
  { value: 'wed', label: '水' },
  { value: 'thu', label: '木' },
  { value: 'fri', label: '金' },
  { value: 'sat', label: '土' },
  { value: 'sun', label: '日' },
]

function addSchedule() {
  autoSettings.value.schedules.push({
    platform: 'uword',
    days: ['mon', 'tue', 'wed', 'thu', 'fri'],
    times: ['08:30'],
    enabled: true,
  })
}

function addGenConfig() {
  autoSettings.value.generation.push({
    platform: 'uword',
    sources: [],
    style_note: '',
  })
}

async function fetchAutoSettings() {
  try {
    const res = await fetch(`${BASE}/api/auto-settings`)
    autoSettings.value = await res.json()
  } catch {
    showToast('自動設定の取得に失敗しました', 'error')
  }
}

async function saveAutoSettings() {
  savingSettings.value = true
  try {
    await fetch(`${BASE}/api/auto-settings`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(autoSettings.value),
    })
    await fetchJobs()
    showToast('自動設定を保存しました', 'success')
  } catch {
    showToast('自動設定の保存に失敗しました', 'error')
  } finally {
    savingSettings.value = false
  }
}

async function fetchJobs() {
  try {
    const res = await fetch(`${BASE}/api/scheduler/jobs`)
    scheduledJobs.value = await res.json()
  } catch {
    // silent fail
  }
}

async function runNow(platform: string) {
  try {
    const res = await fetch(`${BASE}/api/scheduler/run-now/${platform}`, { method: 'POST' })
    const d = await res.json()
    showToast(d.message || '実行を開始しました', 'success')
  } catch {
    showToast('実行に失敗しました', 'error')
  }
}

// ──────────────────────────────────────────────────────────
// AI コンテンツ生成
// ──────────────────────────────────────────────────────────

async function summarizeUrl() {
  summarizing.value = true
  summarizeError.value = ''
  summaryText.value = ''
  try {
    const res = await fetch(`${BASE}/api/summarize`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ url: generateSource.value }),
    })
    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: res.statusText }))
      summarizeError.value = `要約失敗: ${err.detail || res.statusText}`
      return
    }
    const data = await res.json()
    summaryText.value = data.summary || ''
    if (data.title && !generateSource.value.includes(data.title)) {
      showToast(`「${data.title}」を要約しました`, 'success')
    } else {
      showToast('要約が完了しました', 'success')
    }
  } catch {
    summarizeError.value = 'ネットワークエラー: バックエンドに接続できません'
  } finally {
    summarizing.value = false
  }
}

async function generateContent() {
  generating.value = true
  generateError.value = ''
  // URLモードは要約テキストを source として渡す
  const effectiveSourceType = sourceType.value === 'url' && summaryText.value ? 'topic' : sourceType.value
  const effectiveSource = sourceType.value === 'url' && summaryText.value
    ? summaryText.value
    : generateSource.value
  try {
    const res = await fetch(`${BASE}/api/generate`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        source_type: effectiveSourceType,
        source: effectiveSource,
        platform: activePlatform.value,
        tone: selectedTone.value,
        custom_style: customStyle.value,
      }),
    })
    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: res.statusText }))
      generateError.value = `生成失敗: ${err.detail || res.statusText}`
      return
    }
    const data = await res.json()
    if (data.content) {
      title.value = data.title || ''
      content.value = data.content
      if (data.hashtags?.length) {
        // 修正4: 生成されたハッシュタグをチップリストに変換
        hashtagList.value = data.hashtags.map((h: string) => h.trim().replace(/^#/, '')).filter(Boolean)
      }
    }
  } catch {
    generateError.value = 'ネットワークエラー: バックエンドに接続できません'
  } finally {
    generating.value = false
  }
}

// ──────────────────────────────────────────────────────────
// 画像選択
// ──────────────────────────────────────────────────────────

function onImageSelect(e: Event) {
  const input = e.target as HTMLInputElement
  imageFile.value = input.files?.[0] ?? null
}

// ──────────────────────────────────────────────────────────
// 投稿
// ──────────────────────────────────────────────────────────

async function submitPost() {
  loading.value = true
  result.value = null
  repairLogs.value = []
  const platform = activePlatform.value

  const formData = new FormData()
  formData.append('platform', platform)
  formData.append('title', title.value)
  formData.append('content', content.value)
  formData.append('hashtags', hashtagList.value.join(','))
  if (imageFile.value) formData.append('image', imageFile.value)

  // クレデンシャルを追加
  const c = currentCreds.value as any
  if (c.username) formData.append('cred_username', c.username)
  if (c.password) formData.append('cred_password', c.password)
  if (c.site_url) formData.append('cred_site_url', c.site_url)
  if (c.post_url) formData.append('cred_post_url', c.post_url || '')

  try {
    let res: Response
    if (platform === 'uword' || platform === 'umatching') {
      res = await fetch(`${BASE}/api/post-with-healing`, { method: 'POST', body: formData })
    } else {
      res = await fetch(`${BASE}/api/post`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          platform,
          title: title.value,
          content: content.value,
          hashtags: hashtagList.value,
          image_path: generatedImagePath.value || null,
        }),
      })
    }
    const data = await res.json()
    result.value = { success: data.success, post_url: data.post_url || '', error: data.error || '' }

    // 修復ログを表示
    if (data.healing_log?.length) {
      repairLogs.value = data.healing_log
    }

    if (data.success) {
      showToast('✅ 投稿完了！', 'success')
      await Promise.all([fetchLogs(), fetchTodayPostStatus()])
    } else {
      showToast(`❌ 投稿失敗: ${data.error || '不明なエラー'}`, 'error')
      await fetchTodayPostStatus()
    }
  } catch {
    result.value = { success: false, post_url: '', error: 'ネットワークエラー: バックエンドに接続できません' }
    showToast(`❌ 投稿失敗: ${result.value.error}`, 'error')
    await fetchTodayPostStatus()
  } finally {
    loading.value = false
  }
}

// ──────────────────────────────────────────────────────────
// リトライ・修復
// ──────────────────────────────────────────────────────────

async function retryPost() {
  loading.value = true
  result.value = null
  repairLogs.value = []
  try {
    const res = await fetch(`${BASE}/api/retry`, { method: 'POST' })
    result.value = await res.json()
    if (result.value?.success) {
      showToast('✅ 投稿完了！', 'success')
      await Promise.all([fetchLogs(), fetchTodayPostStatus()])
    } else {
      showToast(`❌ 投稿失敗: ${result.value?.error || '不明なエラー'}`, 'error')
      await fetchTodayPostStatus()
    }
  } catch {
    result.value = { success: false, post_url: '', error: 'ネットワークエラー: バックエンドに接続できません' }
    showToast(`❌ 投稿失敗: ${result.value.error}`, 'error')
    await fetchTodayPostStatus()
  } finally {
    loading.value = false
  }
}

async function repairPost() {
  repairing.value = true
  repairLogs.value = ['修復を開始します...']
  try {
    const res = await fetch(`${BASE}/api/repair`, { method: 'POST' })
    const data = await res.json()
    repairLogs.value = data.logs || []
    result.value = { success: data.success, post_url: data.post_url || '', error: data.error || '' }
    if (data.success) {
      showToast('✅ 投稿完了！', 'success')
      await Promise.all([fetchLogs(), fetchTodayPostStatus()])
    } else {
      showToast(`❌ 投稿失敗: ${data.error || '不明なエラー'}`, 'error')
      await fetchTodayPostStatus()
    }
  } catch {
    repairLogs.value = ['ネットワークエラー: バックエンドに接続できません']
    result.value = { success: false, post_url: '', error: 'ネットワークエラー' }
    showToast(`❌ 投稿失敗: ${result.value.error}`, 'error')
    await fetchTodayPostStatus()
  } finally {
    repairing.value = false
  }
}

// ──────────────────────────────────────────────────────────
// ログ
// ──────────────────────────────────────────────────────────

async function fetchLogs() {
  logsLoading.value = true
  try {
    const res = await fetch(`${BASE}/api/logs?limit=20`)
    logs.value = normalizeLogs(await res.json())
  } catch {
    showToast('ログの取得に失敗しました', 'error')
  } finally {
    logsLoading.value = false
  }
}

function normalizeLogs(payload: unknown): LogEntry[] {
  if (Array.isArray(payload)) return payload as LogEntry[]
  if (payload && typeof payload === 'object' && Array.isArray((payload as { logs?: unknown }).logs)) {
    return (payload as { logs: LogEntry[] }).logs
  }
  return []
}

function isTodayLog(log: LogEntry): boolean {
  if (!log.posted_at || log.status !== 'success') return false
  const postedDate = new Date(log.posted_at)
  if (Number.isNaN(postedDate.getTime())) return false
  const today = new Date()
  return postedDate.toDateString() === today.toDateString()
}

async function fetchTodayPostStatus() {
  todayStatusLoading.value = true
  try {
    const res = await fetch(`${BASE}/api/logs?limit=10`)
    const recentLogs = normalizeLogs(await res.json())
    todayPostCounts.value = recentLogs.reduce<Record<string, number>>((acc, log) => {
      if (isTodayLog(log) && (log.platform === 'uword' || log.platform === 'umatching')) {
        acc[log.platform] = (acc[log.platform] || 0) + 1
      }
      return acc
    }, { uword: 0, umatching: 0 })
  } catch {
    showToast('今日の投稿状況の取得に失敗しました', 'error')
  } finally {
    todayStatusLoading.value = false
  }
}

function formatDate(dt: string | null): string {
  if (!dt) return ''
  try {
    return new Date(dt).toLocaleString('ja-JP', {
      month: '2-digit',
      day: '2-digit',
      hour: '2-digit',
      minute: '2-digit',
    })
  } catch {
    return dt
  }
}

// ──────────────────────────────────────────────────────────
// 定型文
// ──────────────────────────────────────────────────────────

async function fetchBoilerplate() {
  try {
    const res = await fetch(`${BASE}/api/boilerplate`)
    bp.value = await res.json()
  } catch {
    // silent fail
  }
}

async function saveBoilerplate() {
  try {
    await fetch(`${BASE}/api/boilerplate`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(bp.value),
    })
    bpSaved.value = true
    setTimeout(() => { bpSaved.value = false }, 2000)
    showToast('定型文を保存しました', 'success')
  } catch {
    showToast('定型文の保存に失敗しました', 'error')
  }
}

// ──────────────────────────────────────────────────────────
// 週次レビュー
// ──────────────────────────────────────────────────────────

const review = ref<{ summary: Record<string, number>; posts: ReviewPost[]; date: string }>({ summary: {}, posts: [], date: '' })
const runningReview = ref(false)

async function fetchReview() {
  try {
    const res = await fetch(`${BASE}/api/review/latest`)
    review.value = await res.json()
  } catch {
    showToast('レビューの取得に失敗しました', 'error')
  }
}

async function runReview() {
  runningReview.value = true
  try {
    await fetch(`${BASE}/api/review/run`, { method: 'POST' })
    await fetchReview()
  } catch {
    // silent fail
  } finally {
    runningReview.value = false
  }
}

function scoreColor(score: number | null) {
  if (!score) return 'score-na'
  if (score >= 8) return 'score-high'
  if (score >= 5) return 'score-mid'
  return 'score-low'
}

// ──────────────────────────────────────────────────────────
// 診断
// ──────────────────────────────────────────────────────────

const diagnosing = ref(false)
const diagResult = ref<DiagResult | null>(null)

async function diagnose(platform: string) {
  diagnosing.value = true
  diagResult.value = null
  try {
    const res = await fetch(`${BASE}/api/diagnose/${platform}`)
    diagResult.value = await res.json()
  } catch {
    showToast('診断の取得に失敗しました', 'error')
  } finally {
    diagnosing.value = false
  }
}

// ──────────────────────────────────────────────────────────
// ログ詳細
// ──────────────────────────────────────────────────────────

const detailLogs = ref<any[]>([])
const showErrorsOnly = ref(false)
const filteredLogs = computed(() =>
  showErrorsOnly.value ? detailLogs.value.filter((l) => l.status !== 'success') : detailLogs.value
)

async function fetchDetailLogs() {
  try {
    const res = await fetch(`${BASE}/api/logs/detail`)
    detailLogs.value = await res.json()
  } catch {
    // silent fail
  }
}

onMounted(() => {
  fetchPlatforms()
  fetchTones()
  fetchLogs()
  fetchTodayPostStatus()
  fetchBoilerplate()
  fetchAutoSettings()
  fetchJobs()
  fetchReview()
  fetchDetailLogs()
})
</script>

<style scoped>
/* ============================================================ */
/* CSS Variables — Sakura Pastel Design System (案C) */
/* ============================================================ */
:root {
  --bg-card: rgba(255, 255, 255, 0.82);
  --bg-card-inner: rgba(255, 246, 250, 0.9);
  --accent-rose: #e75480;
  --accent-lavender: #9b59b6;
  --accent-pink: #f06292;
  --accent-peach: #ffb3c6;
  --text-main: #3d1a4a;
  --text-sub: #7a4f6d;
  --text-muted: #a07890;
  --border-soft: rgba(231, 84, 128, 0.18);
  --border-lavender: rgba(155, 89, 182, 0.2);
  --shadow-rose: 0 4px 24px rgba(231, 84, 128, 0.1);
  --shadow-card: 0 4px 24px rgba(124, 58, 237, 0.13), 0 1px 6px rgba(231, 84, 128, 0.10);
  --radius-card: 24px;
  --radius-btn: 50px;
  --radius-input: 14px;
}

.page-wrapper {
  max-width: 1200px;
  margin: 0 auto;
  color: var(--text-main);
  min-height: 100vh;
  padding-bottom: 40px;
}

/* ============================================================ */
/* Page-level tabs */
/* ============================================================ */
.page-tabs {
  display: flex;
  gap: 4px;
  margin-bottom: 24px;
  background: rgba(255, 255, 255, 0.7);
  backdrop-filter: blur(16px);
  border-radius: var(--radius-btn);
  padding: 5px;
  width: fit-content;
  border: 1px solid var(--border-soft);
  box-shadow: 0 2px 12px rgba(231, 84, 128, 0.08);
}

.page-tab {
  padding: 8px 22px;
  border-radius: var(--radius-btn);
  border: 1px solid transparent;
  background: transparent;
  color: var(--text-sub);
  font-size: 13px;
  font-weight: 500;
  cursor: pointer;
  transition: all 0.3s;
}

.page-tab.active {
  background: linear-gradient(135deg, var(--accent-rose), var(--accent-lavender));
  color: #fff;
  font-weight: 600;
  box-shadow: 0 4px 16px rgba(231, 84, 128, 0.35);
  border-bottom: 2px solid #7c3aed;
}

.page-tab:not(.active):hover {
  background: rgba(231, 84, 128, 0.08);
  color: var(--accent-rose);
  transform: translateY(-1px);
}

.layout {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 24px;
}

@media (max-width: 768px) {
  .layout {
    grid-template-columns: 1fr;
  }
}

.card {
  background: var(--bg-card);
  backdrop-filter: blur(20px);
  border: 1.5px solid rgba(124, 58, 237, 0.18);
  border-radius: var(--radius-card);
  padding: 24px;
  box-shadow: var(--shadow-card);
  transition: box-shadow 0.3s;
}

.card:hover {
  box-shadow: 0 12px 40px rgba(155, 89, 182, 0.12), 0 4px 12px rgba(231, 84, 128, 0.1);
}

.section-title {
  font-size: 16px;
  font-weight: 700;
  color: var(--text-main);
  margin-bottom: 20px;
  background: linear-gradient(135deg, var(--accent-rose), var(--accent-lavender));
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
  background-clip: text;
}

/* ============================================================ */
/* Platform Tabs (リアルタイム速報 / ミニブログ) */
/* ============================================================ */
.tabs {
  display: flex;
  background: rgba(255, 240, 248, 0.8);
  border-radius: var(--radius-btn);
  padding: 5px;
  border: 1px solid var(--border-soft);
  margin-bottom: 20px;
  box-shadow: inset 0 2px 6px rgba(231, 84, 128, 0.06);
}

.tab {
  flex: 1;
  padding: 8px 16px;
  border-radius: var(--radius-btn);
  border: none;
  background: transparent;
  color: var(--text-sub);
  cursor: pointer;
  font-size: 13px;
  transition: all 0.3s;
}

.tab.active {
  background: linear-gradient(135deg, var(--accent-rose), var(--accent-lavender));
  color: #fff;
  font-weight: 600;
  box-shadow: 0 4px 14px rgba(231, 84, 128, 0.35);
}

.tab:not(.active):hover {
  background: rgba(231, 84, 128, 0.08);
  color: var(--accent-rose);
  transform: translateY(-1px);
}

/* ============================================================ */
/* AI 生成セクション */
/* ============================================================ */
.generate-section {
  background: linear-gradient(135deg, rgba(255, 240, 248, 0.9), rgba(245, 232, 255, 0.9));
  border: 1px solid var(--border-soft);
  border-radius: 18px;
  padding: 16px;
  margin-bottom: 20px;
  box-shadow: 0 2px 12px rgba(231, 84, 128, 0.07);
}

.generate-title {
  font-size: 12px;
  font-weight: 700;
  background: linear-gradient(135deg, var(--accent-rose), var(--accent-lavender));
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
  background-clip: text;
  margin-bottom: 10px;
  text-transform: uppercase;
  letter-spacing: 0.8px;
}

.generate-row {
  display: flex;
  gap: 8px;
  align-items: center;
  flex-wrap: wrap;
}

.generate-select {
  background: rgba(255, 255, 255, 0.9);
  border: 1px solid var(--border-soft);
  border-radius: var(--radius-input);
  color: var(--text-main);
  font-size: 13px;
  padding: 8px 10px;
  cursor: pointer;
  outline: none;
  flex-shrink: 0;
  transition: border-color 0.3s, box-shadow 0.3s;
}

.generate-select:focus {
  border-color: var(--accent-rose);
  box-shadow: 0 0 0 3px rgba(231, 84, 128, 0.12);
}

.generate-input {
  flex: 1;
  min-width: 0;
  background: rgba(255, 255, 255, 0.9);
  border: 1px solid var(--border-soft);
  border-radius: var(--radius-input);
  color: var(--text-main);
  font-size: 13px;
  padding: 8px 12px;
  outline: none;
  font-family: inherit;
  transition: border-color 0.3s, box-shadow 0.3s;
}

.generate-input:focus {
  border-color: var(--accent-rose);
  box-shadow: 0 0 0 3px rgba(231, 84, 128, 0.12);
}

.generate-input::placeholder {
  color: var(--text-muted);
}

.btn-generate {
  padding: 8px 20px;
  background: linear-gradient(135deg, rgba(155, 89, 182, 0.12), rgba(231, 84, 128, 0.12));
  border: 1px solid var(--border-lavender);
  color: var(--accent-lavender);
  border-radius: var(--radius-btn);
  cursor: pointer;
  font-size: 13px;
  font-weight: 600;
  white-space: nowrap;
  flex-shrink: 0;
  transition: all 0.3s;
}

.btn-generate:hover:not(:disabled) {
  background: linear-gradient(135deg, var(--accent-lavender), var(--accent-rose));
  color: #fff;
  border-color: transparent;
  transform: translateY(-2px);
  box-shadow: 0 6px 18px rgba(155, 89, 182, 0.3);
}

.btn-generate:disabled {
  opacity: 0.45;
  cursor: not-allowed;
}

/* 2ステップUI */
.gen-step {
  margin-bottom: 8px;
}

.step-badge {
  display: inline-block;
  font-size: 11px;
  font-weight: 700;
  color: var(--accent-lavender);
  background: rgba(155, 89, 182, 0.1);
  border: 1px solid rgba(155, 89, 182, 0.25);
  border-radius: 12px;
  padding: 2px 10px;
  margin-bottom: 6px;
}

.btn-summarize {
  padding: 8px 16px;
  background: linear-gradient(135deg, rgba(231, 84, 128, 0.1), rgba(155, 89, 182, 0.1));
  border: 1px solid var(--border-rose);
  color: var(--accent-rose);
  border-radius: var(--radius-btn);
  cursor: pointer;
  font-size: 13px;
  font-weight: 600;
  white-space: nowrap;
  flex-shrink: 0;
  transition: all 0.3s;
}

.btn-summarize:hover:not(:disabled) {
  background: linear-gradient(135deg, var(--accent-rose), var(--accent-lavender));
  color: #fff;
  border-color: transparent;
  transform: translateY(-2px);
  box-shadow: 0 6px 18px rgba(231, 84, 128, 0.3);
}

.btn-summarize:disabled {
  opacity: 0.45;
  cursor: not-allowed;
}

.summary-block {
  background: rgba(255, 255, 255, 0.6);
  backdrop-filter: blur(8px);
  border: 1px solid rgba(155, 89, 182, 0.2);
  border-radius: 12px;
  padding: 12px;
  margin-bottom: 12px;
}

.summary-header {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 8px;
}

.summary-hint {
  font-size: 11px;
  color: rgba(80, 60, 80, 0.55);
  flex: 1;
}

.btn-clear-summary {
  font-size: 11px;
  color: rgba(180, 80, 80, 0.7);
  background: none;
  border: 1px solid rgba(180, 80, 80, 0.25);
  border-radius: 8px;
  padding: 2px 8px;
  cursor: pointer;
  transition: all 0.2s;
}

.btn-clear-summary:hover {
  color: #fff;
  background: rgba(180, 80, 80, 0.6);
  border-color: transparent;
}

.summary-textarea {
  width: 100%;
  background: rgba(255, 255, 255, 0.5);
  border: 1px solid rgba(155, 89, 182, 0.2);
  border-radius: 8px;
  padding: 8px 12px;
  font-size: 13px;
  color: var(--text-primary);
  resize: vertical;
  line-height: 1.6;
  box-sizing: border-box;
}

.summary-textarea:focus {
  outline: none;
  border-color: var(--accent-lavender);
  box-shadow: 0 0 0 3px rgba(155, 89, 182, 0.1);
}

.generate-error {
  font-size: 12px;
  color: #e05c7a;
  margin-top: 8px;
  background: rgba(231, 84, 128, 0.08);
  padding: 6px 10px;
  border-radius: 8px;
}

/* ============================================================ */
/* Fields */
/* ============================================================ */
.field {
  margin-bottom: 16px;
}

.label {
  display: flex;
  align-items: center;
  justify-content: space-between;
  font-size: 12px;
  font-weight: 600;
  color: var(--text-sub);
  margin-bottom: 6px;
}

.char-count {
  color: var(--text-muted);
  font-weight: 400;
}

.char-hint {
  color: var(--text-muted);
  font-weight: 400;
}

.input,
.textarea {
  width: 100%;
  background: rgba(255, 255, 255, 0.92);
  border: 1px solid #d1d5db;
  border-radius: var(--radius-input);
  color: var(--text-main);
  font-size: 14px;
  padding: 10px 14px;
  transition: border-color 0.3s, box-shadow 0.3s;
  outline: none;
  font-family: inherit;
  box-sizing: border-box;
}

.input::placeholder,
.textarea::placeholder {
  color: var(--text-muted);
}

.input:focus,
.textarea:focus {
  outline: none;
  border-color: #7c3aed;
  box-shadow: 0 0 0 2px rgba(124, 58, 237, 0.2);
  background: #fff;
}

.textarea {
  resize: vertical;
  min-height: 200px;
}

/* 文字数カウンタ */
.char-counter {
  text-align: right;
  font-size: 12px;
  color: var(--text-muted);
  margin-top: 4px;
}

.char-counter.over-limit {
  color: #e05c7a;
  font-weight: 600;
}

.over-msg {
  margin-left: 4px;
}

/* ============================================================ */
/* ハッシュタグ チップ式UI */
/* ============================================================ */
.hashtag-section {
  margin-bottom: 12px;
}

.hashtag-chips {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  background: rgba(255, 255, 255, 0.9);
  border: 1.5px solid rgba(231, 84, 128, 0.15);
  border-radius: var(--radius-input);
  padding: 8px;
  min-height: 44px;
  align-items: center;
  transition: border-color 0.3s, box-shadow 0.3s;
}

.hashtag-chips:focus-within {
  border-color: var(--accent-rose);
  box-shadow: 0 0 0 3px rgba(231, 84, 128, 0.12);
}

.hashtag-chip-edit {
  background: linear-gradient(135deg, rgba(231, 84, 128, 0.15), rgba(155, 89, 182, 0.15));
  color: var(--accent-rose);
  padding: 4px 10px;
  border-radius: 50px;
  font-size: 13px;
  display: flex;
  align-items: center;
  gap: 4px;
  border: 1px solid rgba(231, 84, 128, 0.25);
}

.chip-remove {
  background: none;
  border: none;
  color: var(--accent-rose);
  cursor: pointer;
  font-size: 14px;
  padding: 0;
  line-height: 1;
  transition: color 0.2s;
}

.chip-remove:hover {
  color: var(--accent-lavender);
}

.hashtag-text-input {
  background: none;
  border: none;
  color: var(--text-main);
  outline: none;
  min-width: 120px;
  font-size: 14px;
  font-family: inherit;
}

.hashtag-text-input::placeholder {
  color: var(--text-muted);
}

.hashtag-hint {
  font-size: 11px;
  color: var(--text-muted);
  margin-top: 4px;
}

/* ============================================================ */
/* 画像アップロード */
/* ============================================================ */
.image-section {
  margin-bottom: 16px;
}

.image-upload-row {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}

.btn-file-label {
  display: inline-block;
  padding: 7px 18px;
  background: rgba(155, 89, 182, 0.08);
  color: var(--accent-lavender);
  border: 1.5px solid rgba(155, 89, 182, 0.3);
  border-radius: var(--radius-btn);
  font-size: 12px;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.3s;
}

.btn-file-label:hover {
  background: var(--accent-lavender);
  color: #fff;
  transform: translateY(-1px);
  box-shadow: 0 4px 14px rgba(155, 89, 182, 0.3);
}

.file-input-hidden {
  display: none;
}

.image-filename {
  font-size: 12px;
  color: #3d9970;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  max-width: 160px;
  font-weight: 600;
}

.image-placeholder {
  font-size: 12px;
  color: var(--text-muted);
}

.btn-clear-image {
  background: none;
  border: none;
  color: var(--text-muted);
  font-size: 13px;
  cursor: pointer;
  padding: 2px 6px;
  border-radius: 4px;
  transition: color 0.2s;
}

.btn-clear-image:hover {
  color: var(--accent-rose);
}

/* ============================================================ */
/* Submit button */
/* ============================================================ */
.btn-submit {
  width: 100%;
  padding: 13px 32px;
  background: linear-gradient(135deg, var(--accent-rose), var(--accent-lavender));
  color: #fff;
  border: none;
  border-radius: var(--radius-btn);
  font-size: 15px;
  font-weight: 700;
  cursor: pointer;
  box-shadow: 0 6px 24px rgba(231, 84, 128, 0.38);
  transition: all 0.3s;
  letter-spacing: 0.05em;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  margin-top: 4px;
}

.btn-submit:hover:not(:disabled) {
  transform: translateY(-3px);
  box-shadow: 0 12px 32px rgba(231, 84, 128, 0.48);
}

.btn-submit:active:not(:disabled) {
  transform: translateY(-1px);
}

.btn-submit:disabled {
  opacity: 0.45;
  transform: none;
  cursor: not-allowed;
}

/* Spinner */
.spinner {
  display: inline-block;
  width: 16px;
  height: 16px;
  border: 2px solid rgba(255, 255, 255, 0.4);
  border-top-color: #fff;
  border-radius: 50%;
  animation: spin 0.7s linear infinite;
}

@keyframes spin {
  to { transform: rotate(360deg); }
}

/* ============================================================ */
/* Result */
/* ============================================================ */
.result {
  margin-top: 12px;
  padding: 12px 16px;
  border-radius: 16px;
  font-size: 13px;
  font-weight: 500;
}

.result-success {
  background: rgba(61, 153, 112, 0.08);
  color: #2d7a5a;
  border: 1px solid rgba(61, 153, 112, 0.25);
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}

.result-error {
  background: rgba(231, 84, 128, 0.08);
  color: #c0394f;
  border: 1px solid rgba(231, 84, 128, 0.25);
}

.post-link {
  color: #2d7a5a;
  text-decoration: underline;
  font-weight: 600;
}

.post-link:hover {
  color: #1a5c3f;
}

/* ============================================================ */
/* 定型文パネル */
/* ============================================================ */
.boilerplate-panel {
  margin-top: 20px;
  border: 1px solid rgba(231, 84, 128, 0.15);
  border-radius: 18px;
  overflow: hidden;
  background: rgba(255, 255, 255, 0.6);
}

.boilerplate-summary {
  padding: 10px 16px;
  background: rgba(255, 240, 248, 0.7);
  color: var(--text-sub);
  font-size: 12px;
  font-weight: 600;
  cursor: pointer;
  user-select: none;
  list-style: none;
  display: flex;
  align-items: center;
  gap: 6px;
  transition: color 0.2s, background 0.2s;
}

.boilerplate-summary:hover {
  color: var(--accent-rose);
  background: rgba(231, 84, 128, 0.06);
}

.boilerplate-panel[open] .boilerplate-summary {
  border-bottom: 1px solid rgba(231, 84, 128, 0.12);
}

.bp-form {
  padding: 14px;
  background: rgba(255, 255, 255, 0.7);
}

.bp-form .textarea {
  min-height: unset;
}

.btn-save-bp {
  padding: 8px 20px;
  background: linear-gradient(135deg, var(--accent-rose), var(--accent-lavender));
  color: #fff;
  border: none;
  border-radius: var(--radius-btn);
  font-size: 13px;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.3s;
  box-shadow: 0 4px 14px rgba(231, 84, 128, 0.28);
}

.btn-save-bp:hover {
  transform: translateY(-2px);
  box-shadow: 0 8px 20px rgba(231, 84, 128, 0.38);
}

.bp-saved {
  margin-left: 10px;
  font-size: 12px;
  color: #2d7a5a;
  font-weight: 600;
}

/* ============================================================ */
/* Logs */
/* ============================================================ */
.logs-card {
  display: flex;
  flex-direction: column;
}

.today-status-card {
  background: rgba(255, 255, 255, 0.72);
  border: 1px solid rgba(231, 84, 128, 0.12);
  border-radius: 16px;
  padding: 14px;
  margin-bottom: 16px;
}

.today-status-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 10px;
}

.today-status-header .section-title {
  margin-bottom: 0;
}

.today-status-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.today-status-badge {
  display: inline-flex;
  align-items: center;
  width: fit-content;
  max-width: 100%;
  padding: 7px 12px;
  border-radius: 999px;
  background: rgba(155, 89, 182, 0.08);
  border: 1px solid rgba(155, 89, 182, 0.18);
  color: var(--accent-lavender);
  font-size: 13px;
  font-weight: 700;
}

.today-status-badge.complete {
  background: rgba(45, 122, 90, 0.1);
  border-color: rgba(45, 122, 90, 0.2);
  color: #2d7a5a;
}

.logs-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 16px;
}

.logs-header .section-title {
  margin-bottom: 0;
}

.btn-refresh {
  padding: 6px 16px;
  background: rgba(255, 255, 255, 0.8);
  color: var(--text-sub);
  border: 1px solid var(--border-soft);
  border-radius: var(--radius-btn);
  font-size: 12px;
  font-weight: 500;
  cursor: pointer;
  transition: all 0.3s;
}

.btn-refresh:hover:not(:disabled) {
  background: rgba(231, 84, 128, 0.08);
  color: var(--accent-rose);
  border-color: var(--accent-rose);
  transform: translateY(-1px);
}

.btn-refresh:disabled {
  opacity: 0.45;
  cursor: not-allowed;
}

.logs-empty {
  text-align: center;
  color: var(--text-muted);
  padding: 40px 0;
  font-size: 13px;
}

.logs-list {
  list-style: none;
  display: flex;
  flex-direction: column;
  gap: 8px;
  overflow-y: auto;
  max-height: 600px;
}

.log-item {
  background: rgba(255, 255, 255, 0.75);
  border: 1px solid rgba(231, 84, 128, 0.1);
  border-radius: 16px;
  padding: 12px 14px;
  transition: border-color 0.3s, box-shadow 0.3s;
}

.log-item:hover {
  border-color: rgba(231, 84, 128, 0.25);
  box-shadow: 0 4px 16px rgba(231, 84, 128, 0.08);
}

.log-top {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 4px;
}

.badge {
  display: inline-block;
  padding: 3px 10px;
  border-radius: 50px;
  font-size: 11px;
  font-weight: 600;
}

.badge-success {
  background: rgba(45, 122, 90, 0.1);
  color: #2d7a5a;
}

.badge-error {
  background: rgba(231, 84, 128, 0.1);
  color: #c0394f;
}

.log-platform {
  font-size: 11px;
  color: var(--accent-lavender);
  font-weight: 600;
}

.log-date {
  margin-left: auto;
  font-size: 11px;
  color: var(--text-muted);
}

.log-title {
  font-size: 13px;
  font-weight: 600;
  color: var(--text-main);
  margin-bottom: 2px;
}

.log-content {
  font-size: 12px;
  color: var(--text-sub);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.log-error {
  font-size: 11px;
  color: #c0394f;
  margin-top: 4px;
}

/* ============================================================ */
/* リトライ・修復 */
/* ============================================================ */
.retry-actions {
  display: flex;
  gap: 8px;
  margin-top: 8px;
}

.btn-retry {
  background: rgba(231, 84, 128, 0.08);
  color: var(--accent-rose);
  border: 1px solid rgba(231, 84, 128, 0.25);
  padding: 8px 18px;
  border-radius: var(--radius-btn);
  cursor: pointer;
  font-weight: 600;
  font-size: 13px;
  transition: all 0.3s;
}

.btn-retry:hover:not(:disabled) {
  background: var(--accent-rose);
  color: #fff;
  transform: translateY(-1px);
}

.btn-retry:disabled {
  opacity: 0.45;
  cursor: not-allowed;
}

.btn-repair {
  background: rgba(155, 89, 182, 0.08);
  color: var(--accent-lavender);
  border: 1px solid rgba(155, 89, 182, 0.25);
  padding: 8px 18px;
  border-radius: var(--radius-btn);
  cursor: pointer;
  font-weight: 600;
  font-size: 13px;
  transition: all 0.3s;
}

.btn-repair:hover:not(:disabled) {
  background: var(--accent-lavender);
  color: #fff;
  transform: translateY(-1px);
}

.btn-repair:disabled {
  opacity: 0.45;
  cursor: not-allowed;
}

.repair-log {
  margin-top: 12px;
  background: rgba(255, 255, 255, 0.7);
  border: 1px solid var(--border-soft);
  border-radius: 16px;
  padding: 12px;
}

.repair-log h4 {
  margin: 0 0 8px;
  color: var(--text-sub);
  font-size: 12px;
  font-weight: 600;
}

.log-entries {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.log-entry {
  font-family: monospace;
  font-size: 12px;
  color: var(--text-sub);
  padding: 2px 0;
}

/* ============================================================ */
/* プレビューモーダル */
/* ============================================================ */
.preview-overlay {
  position: fixed;
  inset: 0;
  background: rgba(61, 26, 74, 0.45);
  backdrop-filter: blur(12px);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 1000;
}

.preview-modal {
  background: linear-gradient(135deg, #fff5f8, #f9f0ff);
  border: 1px solid rgba(231, 84, 128, 0.2);
  border-radius: 28px;
  padding: 28px;
  max-width: 560px;
  width: 90%;
  max-height: 80vh;
  overflow-y: auto;
  box-shadow: 0 24px 64px rgba(155, 89, 182, 0.2), 0 8px 24px rgba(231, 84, 128, 0.12);
}

.preview-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 16px;
}

.preview-header h3 {
  margin: 0;
  color: var(--text-main);
  font-size: 16px;
  font-weight: 700;
  background: linear-gradient(135deg, var(--accent-rose), var(--accent-lavender));
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
  background-clip: text;
}

.btn-close {
  background: rgba(231, 84, 128, 0.08);
  border: 1px solid rgba(231, 84, 128, 0.2);
  color: var(--text-sub);
  font-size: 18px;
  cursor: pointer;
  padding: 4px 10px;
  border-radius: 50%;
  line-height: 1;
  transition: all 0.2s;
}

.btn-close:hover {
  background: var(--accent-rose);
  color: #fff;
  border-color: transparent;
}

.preview-platform {
  margin-bottom: 12px;
}

.preview-title {
  font-weight: 700;
  color: var(--text-main);
  font-size: 16px;
  margin-bottom: 8px;
  padding-bottom: 8px;
  border-bottom: 1px solid var(--border-soft);
}

.preview-body {
  color: var(--text-sub);
  white-space: pre-wrap;
  line-height: 1.7;
  margin-bottom: 12px;
  background: rgba(255, 255, 255, 0.8);
  padding: 14px;
  border-radius: 14px;
  font-size: 14px;
  border: 1px solid rgba(231, 84, 128, 0.1);
}

.preview-hashtags {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  margin-bottom: 12px;
}

.hashtag-chip {
  background: linear-gradient(135deg, rgba(231, 84, 128, 0.12), rgba(155, 89, 182, 0.12));
  color: var(--accent-rose);
  padding: 4px 14px;
  border-radius: 50px;
  font-size: 12px;
  border: 1px solid rgba(231, 84, 128, 0.2);
  font-weight: 500;
}

.preview-char-count {
  text-align: right;
  font-size: 12px;
  color: var(--text-muted);
  margin-bottom: 16px;
}

.preview-char-count.over-limit {
  color: #c0394f;
  font-weight: 600;
}

.preview-actions {
  display: flex;
  gap: 8px;
  justify-content: flex-end;
}

.btn-cancel-preview {
  background: rgba(255, 255, 255, 0.8);
  color: var(--text-sub);
  border: 1px solid var(--border-soft);
  padding: 10px 20px;
  border-radius: var(--radius-btn);
  cursor: pointer;
  font-size: 14px;
  font-weight: 500;
  transition: all 0.3s;
}

.btn-cancel-preview:hover {
  background: rgba(231, 84, 128, 0.06);
  color: var(--accent-rose);
  border-color: var(--accent-rose);
}

.btn-confirm-post {
  background: linear-gradient(135deg, var(--accent-rose), var(--accent-lavender));
  color: #fff;
  border: none;
  padding: 10px 28px;
  border-radius: var(--radius-btn);
  cursor: pointer;
  font-weight: 700;
  font-size: 14px;
  box-shadow: 0 6px 18px rgba(231, 84, 128, 0.35);
  transition: all 0.3s;
}

.btn-confirm-post:hover:not(:disabled) {
  transform: translateY(-2px);
  box-shadow: 0 10px 28px rgba(231, 84, 128, 0.48);
}

.btn-confirm-post:disabled {
  opacity: 0.45;
  transform: none;
  cursor: not-allowed;
}

/* ============================================================ */
/* 自動設定タブ */
/* ============================================================ */
.auto-settings {
  padding: 8px 0;
}

.settings-section {
  background: var(--bg-card);
  border: 1px solid rgba(231, 84, 128, 0.12);
  border-radius: var(--radius-card);
  padding: 20px;
  margin-bottom: 16px;
  box-shadow: var(--shadow-card);
}

.settings-section h3 {
  margin: 0 0 16px;
  color: var(--text-main);
  font-size: 15px;
  font-weight: 700;
}

.settings-section h4 {
  margin: 12px 0 8px;
  color: var(--text-sub);
  font-size: 12px;
  font-weight: 600;
}

.schedule-card,
.gen-card {
  background: rgba(255, 246, 250, 0.8);
  border: 1px solid rgba(231, 84, 128, 0.1);
  border-radius: 16px;
  padding: 16px;
  margin-bottom: 12px;
}

.schedule-header,
.gen-header {
  display: flex;
  gap: 8px;
  align-items: center;
  margin-bottom: 12px;
  flex-wrap: wrap;
}

.schedule-header select,
.gen-header select {
  background: rgba(255, 255, 255, 0.9);
  border: 1px solid var(--border-soft);
  color: var(--text-main);
  padding: 6px 10px;
  border-radius: 10px;
  font-size: 13px;
  outline: none;
}

.day-selector {
  display: flex;
  gap: 12px;
  flex-wrap: wrap;
  margin-bottom: 12px;
}

.day-selector label {
  display: flex;
  align-items: center;
  gap: 4px;
  color: var(--text-sub);
  cursor: pointer;
  font-size: 13px;
}

.time-entries {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.time-row {
  display: flex;
  gap: 8px;
  align-items: center;
}

.time-input {
  background: rgba(255, 255, 255, 0.9);
  border: 1px solid var(--border-soft);
  color: var(--text-main);
  padding: 4px 10px;
  border-radius: 10px;
  font-size: 13px;
  outline: none;
}

.source-row {
  display: flex;
  gap: 8px;
  align-items: center;
  margin-bottom: 6px;
  flex-wrap: wrap;
}

.source-row label {
  display: flex;
  align-items: center;
  gap: 4px;
  color: var(--text-sub);
  font-size: 13px;
  white-space: nowrap;
}

.src-type {
  width: 100px;
  background: rgba(255, 255, 255, 0.9);
  border: 1px solid var(--border-soft);
  color: var(--text-main);
  padding: 4px;
  border-radius: 8px;
  font-size: 13px;
  outline: none;
}

.src-value {
  flex: 1;
  min-width: 200px;
  background: rgba(255, 255, 255, 0.9);
  border: 1px solid var(--border-soft);
  color: var(--text-main);
  padding: 6px 10px;
  border-radius: 10px;
  font-size: 13px;
  outline: none;
}

.style-note {
  margin-bottom: 12px;
}

.style-note label {
  display: block;
  color: var(--text-sub);
  font-size: 12px;
  font-weight: 600;
  margin-bottom: 4px;
}

.style-note input {
  width: 100%;
  background: rgba(255, 255, 255, 0.9);
  border: 1.5px solid rgba(231, 84, 128, 0.15);
  color: var(--text-main);
  padding: 8px 12px;
  border-radius: 10px;
  box-sizing: border-box;
  font-size: 13px;
  outline: none;
  transition: border-color 0.3s, box-shadow 0.3s;
}

.style-note input:focus {
  border-color: var(--accent-rose);
  box-shadow: 0 0 0 3px rgba(231, 84, 128, 0.1);
}

.sources-list {
  background: rgba(255, 246, 250, 0.7);
  border-radius: 12px;
  padding: 12px;
  border: 1px solid rgba(231, 84, 128, 0.08);
}

.btn-add {
  background: rgba(155, 89, 182, 0.07);
  color: var(--accent-lavender);
  border: 1.5px dashed rgba(155, 89, 182, 0.3);
  padding: 8px 16px;
  border-radius: var(--radius-btn);
  cursor: pointer;
  width: 100%;
  margin-top: 8px;
  font-size: 13px;
  font-weight: 500;
  transition: all 0.3s;
}

.btn-add:hover {
  background: rgba(155, 89, 182, 0.15);
  border-color: var(--accent-lavender);
  transform: translateY(-1px);
}

.btn-add-time {
  background: rgba(255, 255, 255, 0.7);
  color: var(--text-sub);
  border: 1px dashed var(--border-soft);
  padding: 4px 12px;
  border-radius: var(--radius-btn);
  cursor: pointer;
  font-size: 12px;
  margin-top: 4px;
  transition: all 0.3s;
}

.btn-add-time:hover {
  color: var(--accent-rose);
  border-color: var(--accent-rose);
}

.btn-remove {
  background: rgba(231, 84, 128, 0.08);
  color: #c0394f;
  border: 1px solid rgba(231, 84, 128, 0.2);
  padding: 4px 10px;
  border-radius: var(--radius-btn);
  cursor: pointer;
  font-size: 12px;
  transition: all 0.3s;
}

.btn-remove:hover {
  background: rgba(231, 84, 128, 0.18);
}

.btn-small {
  background: rgba(255, 255, 255, 0.7);
  color: var(--text-sub);
  border: 1px solid rgba(231, 84, 128, 0.15);
  padding: 2px 8px;
  border-radius: var(--radius-btn);
  cursor: pointer;
  font-size: 12px;
  transition: all 0.3s;
}

.btn-small:hover {
  color: var(--text-main);
  background: rgba(255, 255, 255, 0.95);
}

.btn-save-settings {
  background: linear-gradient(135deg, var(--accent-rose), var(--accent-lavender));
  color: #fff;
  border: none;
  padding: 11px 28px;
  border-radius: var(--radius-btn);
  cursor: pointer;
  font-weight: 700;
  font-size: 15px;
  box-shadow: 0 6px 22px rgba(231, 84, 128, 0.35);
  transition: all 0.3s;
}

.btn-save-settings:hover:not(:disabled) {
  transform: translateY(-2px);
  box-shadow: 0 10px 30px rgba(231, 84, 128, 0.48);
}

.btn-save-settings:disabled {
  opacity: 0.45;
  transform: none;
  cursor: not-allowed;
}

.settings-actions {
  display: flex;
  flex-direction: column;
  gap: 12px;
  margin-bottom: 16px;
}

.test-run {
  display: flex;
  gap: 8px;
  align-items: center;
  flex-wrap: wrap;
  color: var(--text-sub);
  font-size: 13px;
}

.btn-run-now {
  background: rgba(45, 122, 90, 0.08);
  color: #2d7a5a;
  border: 1px solid rgba(45, 122, 90, 0.25);
  padding: 8px 18px;
  border-radius: var(--radius-btn);
  cursor: pointer;
  font-size: 13px;
  font-weight: 600;
  transition: all 0.3s;
}

.btn-run-now:hover {
  background: rgba(45, 122, 90, 0.15);
  transform: translateY(-1px);
}

.job-row {
  display: flex;
  gap: 16px;
  align-items: center;
  padding: 10px 14px;
  background: rgba(255, 255, 255, 0.75);
  border: 1px solid rgba(231, 84, 128, 0.1);
  border-radius: 12px;
  margin-bottom: 6px;
  font-size: 13px;
  color: var(--text-sub);
}

.job-row code {
  color: var(--accent-lavender);
  font-size: 12px;
  font-weight: 600;
}

.btn-refresh-jobs {
  background: rgba(255, 255, 255, 0.8);
  color: var(--text-sub);
  border: 1px solid var(--border-soft);
  padding: 6px 14px;
  border-radius: var(--radius-btn);
  cursor: pointer;
  font-size: 12px;
  margin-top: 8px;
  transition: all 0.3s;
}

.btn-refresh-jobs:hover {
  color: var(--accent-rose);
  border-color: var(--accent-rose);
  transform: translateY(-1px);
}

.empty {
  color: var(--text-muted);
  font-size: 13px;
  padding: 8px 0;
}

.toggle {
  display: flex;
  align-items: center;
  gap: 6px;
  cursor: pointer;
  color: var(--text-sub);
  font-size: 13px;
}

/* ============================================================ */
/* 週次レビュータブ */
/* ============================================================ */
.review-tab { padding: 8px 0; }

.review-summary { display: flex; gap: 12px; margin-bottom: 16px; flex-wrap: wrap; }

.summary-card {
  background: var(--bg-card);
  border-radius: 18px;
  padding: 18px 22px;
  text-align: center;
  min-width: 100px;
  border: 1px solid rgba(231, 84, 128, 0.12);
  box-shadow: var(--shadow-card);
  transition: box-shadow 0.3s;
}

.summary-card:hover {
  box-shadow: 0 8px 28px rgba(155, 89, 182, 0.14);
}

.summary-card.accent { border-color: rgba(155, 89, 182, 0.3); }
.summary-card.green { border-color: rgba(45, 122, 90, 0.3); }
.summary-card.red { border-color: rgba(231, 84, 128, 0.3); }

.sc-value { font-size: 28px; font-weight: 700; color: var(--text-main); }
.sc-label { font-size: 12px; color: var(--text-sub); margin-top: 4px; font-weight: 500; }

.review-actions { display: flex; gap: 8px; align-items: center; margin-bottom: 16px; flex-wrap: wrap; }
.review-date { color: var(--text-muted); font-size: 13px; }

.post-cards { display: flex; flex-direction: column; gap: 12px; }

.post-card {
  background: var(--bg-card);
  border-radius: 18px;
  padding: 16px;
  border: 1px solid rgba(231, 84, 128, 0.1);
  box-shadow: var(--shadow-card);
  transition: box-shadow 0.3s;
}

.post-card:hover {
  box-shadow: 0 8px 28px rgba(155, 89, 182, 0.1);
}

.post-card-header { display: flex; gap: 8px; align-items: center; margin-bottom: 8px; flex-wrap: wrap; }

.score-badge { padding: 3px 12px; border-radius: 50px; font-weight: 700; font-size: 13px; }
.score-high { background: rgba(45, 122, 90, 0.1); color: #2d7a5a; }
.score-mid { background: rgba(231, 84, 128, 0.1); color: var(--accent-rose); }
.score-low { background: rgba(192, 57, 79, 0.1); color: #c0394f; }
.score-na { background: rgba(155, 89, 182, 0.08); color: var(--text-sub); }

.platform-badge {
  background: linear-gradient(135deg, rgba(231, 84, 128, 0.1), rgba(155, 89, 182, 0.1));
  color: var(--accent-rose);
  padding: 2px 12px;
  border-radius: 50px;
  font-size: 12px;
  border: 1px solid rgba(231, 84, 128, 0.2);
  font-weight: 500;
}

.post-title { color: var(--text-main); font-weight: 600; }
.post-meta { color: var(--text-muted); font-size: 12px; margin-bottom: 6px; }
.post-content-preview { color: var(--text-sub); font-size: 13px; margin-bottom: 8px; }

.ai-eval summary { color: var(--accent-lavender); cursor: pointer; font-size: 13px; font-weight: 600; }

.eval-table { width: 100%; border-collapse: collapse; margin-top: 8px; font-size: 13px; }
.eval-table td { padding: 4px 8px; border-bottom: 1px solid rgba(231, 84, 128, 0.08); color: var(--text-sub); }
.eval-table td:first-child { color: var(--text-muted); width: 100px; }
.warn-text { color: #b07800; }

/* ============================================================ */
/* 診断タブ */
/* ============================================================ */
.diagnose-tab { padding: 8px 0; }
.diagnose-tab h3 { color: var(--text-main); margin-bottom: 16px; font-weight: 700; }
.diagnose-buttons { display: flex; gap: 8px; margin-bottom: 16px; flex-wrap: wrap; }

.btn-diagnose {
  background: rgba(155, 89, 182, 0.08);
  color: var(--accent-lavender);
  border: 1.5px solid rgba(155, 89, 182, 0.3);
  padding: 10px 22px;
  border-radius: var(--radius-btn);
  cursor: pointer;
  font-weight: 600;
  transition: all 0.3s;
}

.btn-diagnose:disabled { opacity: 0.45; cursor: not-allowed; }

.btn-diagnose:not(:disabled):hover {
  background: var(--accent-lavender);
  color: #fff;
  transform: translateY(-2px);
  box-shadow: 0 6px 18px rgba(155, 89, 182, 0.3);
}

.diagnosing-msg { color: var(--text-sub); padding: 16px; }

.diag-result {
  background: var(--bg-card);
  border-radius: var(--radius-card);
  padding: 16px;
  border: 1px solid rgba(231, 84, 128, 0.12);
  box-shadow: var(--shadow-card);
}

.diag-header { display: flex; gap: 12px; align-items: center; margin-bottom: 12px; flex-wrap: wrap; }
.status-ok { color: #2d7a5a; font-weight: 700; }
.status-error { color: #c0394f; font-weight: 700; }

.diag-platform {
  background: rgba(155, 89, 182, 0.08);
  color: var(--accent-lavender);
  padding: 2px 12px;
  border-radius: 50px;
  font-size: 12px;
  font-weight: 500;
}

.diag-time { color: var(--text-muted); font-size: 12px; }

.checks-list { display: flex; flex-direction: column; gap: 8px; }

.check-item {
  display: flex;
  gap: 8px;
  align-items: flex-start;
  padding: 10px 14px;
  background: rgba(255, 255, 255, 0.75);
  border: 1px solid rgba(231, 84, 128, 0.08);
  border-radius: 14px;
  transition: border-color 0.2s;
}

.check-item:hover {
  border-color: rgba(231, 84, 128, 0.2);
}

.check-icon { font-size: 16px; flex-shrink: 0; }
.check-label { color: var(--text-main); min-width: 120px; font-size: 13px; font-weight: 500; }
.check-detail { color: var(--text-sub); font-size: 12px; font-family: monospace; }

/* ============================================================ */
/* ログ詳細タブ */
/* ============================================================ */
.logs-tab { padding: 8px 0; }
.logs-tab h3 { color: var(--text-main); margin-bottom: 12px; font-weight: 700; }
.logs-filter { margin-bottom: 12px; color: var(--text-sub); font-size: 13px; }
.detail-logs { display: flex; flex-direction: column; gap: 8px; }

.detail-log-item {
  background: rgba(255, 255, 255, 0.78);
  border-radius: 16px;
  padding: 12px 14px;
  border-left: 3px solid rgba(231, 84, 128, 0.15);
  border-top: 1px solid rgba(231, 84, 128, 0.08);
  border-right: 1px solid rgba(231, 84, 128, 0.08);
  border-bottom: 1px solid rgba(231, 84, 128, 0.08);
}

.log-success { border-left-color: #2d7a5a; }
.log-error { border-left-color: #c0394f; }

.log-row-header { display: flex; gap: 8px; align-items: center; margin-bottom: 6px; flex-wrap: wrap; }

.log-status-badge {
  padding: 3px 10px;
  border-radius: 50px;
  font-size: 11px;
  font-weight: 600;
  text-transform: uppercase;
}

.log-status-badge.success { background: rgba(45, 122, 90, 0.1); color: #2d7a5a; }
.log-status-badge.error { background: rgba(192, 57, 79, 0.1); color: #c0394f; }

.log-content-preview { color: var(--text-sub); font-size: 12px; margin-bottom: 4px; font-family: monospace; }
.log-error-msg { color: #c0394f; font-size: 12px; margin-top: 4px; }
.log-retry { color: var(--accent-rose); font-size: 11px; font-weight: 600; }

/* ============================================================ */
/* トースト通知 */
/* ============================================================ */
.toast {
  position: fixed;
  top: 20px;
  right: 20px;
  padding: 14px 24px;
  border-radius: var(--radius-btn);
  font-size: 13px;
  font-weight: 600;
  z-index: 9999;
  max-width: 320px;
  box-shadow: 0 8px 32px rgba(155, 89, 182, 0.2);
  backdrop-filter: blur(12px);
}

.toast-success {
  background: #2d7a5a;
  border: 1.5px solid rgba(45, 122, 90, 0.3);
  color: #fff;
}

.toast-error {
  background: #c0394f;
  border: 1.5px solid rgba(192, 57, 79, 0.3);
  color: #fff;
}

.toast-info {
  background: rgba(255, 255, 255, 0.92);
  border: 1.5px solid rgba(155, 89, 182, 0.3);
  color: var(--accent-lavender);
}

.toast-enter-active, .toast-leave-active { transition: opacity 0.3s, transform 0.3s; }
.toast-enter-from, .toast-leave-to { opacity: 0; transform: translateY(-8px); }

/* ============================================================ */
/* クレデンシャル設定パネル */
/* ============================================================ */
.creds-panel {
  background: rgba(255, 255, 255, 0.7);
  border: 1px solid rgba(231, 84, 128, 0.15);
  border-radius: 18px;
  padding: 16px;
  margin-top: 20px;
}

.creds-panel summary {
  color: var(--accent-lavender);
  cursor: pointer;
  font-weight: 600;
  font-size: 13px;
  user-select: none;
  list-style: none;
  display: flex;
  align-items: center;
  gap: 6px;
  transition: color 0.2s;
}

.creds-panel summary:hover { color: var(--accent-rose); }
.creds-panel[open] summary { margin-bottom: 12px; }
.creds-form { margin-top: 4px; }

.settings-platform-title {
  color: var(--text-main);
  font-size: 13px;
  font-weight: 700;
  margin: 16px 0 10px;
}

.settings-platform-title:first-child {
  margin-top: 0;
}

.creds-grid {
  display: grid;
  grid-template-columns: 160px 1fr;
  gap: 8px 12px;
  align-items: center;
  margin-bottom: 12px;
}

.creds-grid label { color: var(--text-sub); font-size: 13px; font-weight: 500; }

.creds-grid input {
  background: rgba(255, 255, 255, 0.92);
  border: 1.5px solid rgba(231, 84, 128, 0.15);
  color: var(--text-main);
  padding: 8px 12px;
  border-radius: 10px;
  font-size: 13px;
  outline: none;
  transition: border-color 0.3s, box-shadow 0.3s;
  box-sizing: border-box;
}

.creds-grid input:focus {
  border-color: var(--accent-rose);
  box-shadow: 0 0 0 3px rgba(231, 84, 128, 0.1);
}

.btn-save-creds {
  background: linear-gradient(135deg, rgba(231, 84, 128, 0.12), rgba(155, 89, 182, 0.12));
  color: var(--accent-rose);
  border: 1px solid rgba(231, 84, 128, 0.3);
  padding: 8px 18px;
  border-radius: var(--radius-btn);
  cursor: pointer;
  font-size: 13px;
  font-weight: 600;
  transition: all 0.3s;
}

.btn-save-creds:hover {
  background: linear-gradient(135deg, var(--accent-rose), var(--accent-lavender));
  color: #fff;
  border-color: transparent;
  transform: translateY(-1px);
}

.creds-note { color: var(--text-muted); font-size: 11px; margin-top: 8px; margin-bottom: 0; }

/* ============================================================ */
/* トーン設定 */
/* ============================================================ */
.tone-section { margin: 12px 0; }
.tone-label { display: block; color: var(--text-sub); font-size: 12px; font-weight: 600; margin-bottom: 8px; }
.tone-chips { display: flex; flex-wrap: wrap; gap: 6px; margin-bottom: 8px; }

.tone-chip {
  background: rgba(255, 255, 255, 0.8);
  border: 1.5px solid rgba(231, 84, 128, 0.15);
  color: var(--text-sub);
  border-radius: 50px;
  padding: 6px 16px;
  font-size: 12px;
  cursor: pointer;
  transition: all 0.3s;
}

.tone-chip:hover {
  border-color: var(--accent-rose);
  color: var(--accent-rose);
  background: rgba(231, 84, 128, 0.06);
  transform: translateY(-1px);
}

.tone-chip-active {
  background: linear-gradient(135deg, rgba(231, 84, 128, 0.15), rgba(155, 89, 182, 0.15));
  border-color: var(--accent-rose);
  color: var(--accent-rose);
  font-weight: 600;
}

.custom-style-row { margin-top: 6px; }

.custom-style-input {
  width: 100%;
  background: rgba(255, 255, 255, 0.9);
  border: 1.5px solid rgba(231, 84, 128, 0.15);
  color: var(--text-main);
  padding: 8px 12px;
  border-radius: 10px;
  font-size: 12px;
  box-sizing: border-box;
  outline: none;
  transition: border-color 0.3s, box-shadow 0.3s;
}

.custom-style-input:focus {
  border-color: var(--accent-rose);
  box-shadow: 0 0 0 3px rgba(231, 84, 128, 0.1);
}

.custom-style-input::placeholder { color: var(--text-muted); }

/* Platform Grid */
.platform-grid {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  margin-bottom: 16px;
}

.platform-btn {
  display: flex;
  align-items: center;
  gap: 4px;
  padding: 6px 12px;
  background: rgba(255, 255, 255, 0.6);
  border: 1px solid rgba(155, 89, 182, 0.2);
  border-radius: 20px;
  cursor: pointer;
  font-size: 12px;
  color: var(--text-secondary, #888);
  transition: all 0.2s;
  position: relative;
}

.platform-btn:hover {
  border-color: var(--accent-lavender);
  color: var(--accent-lavender);
  background: rgba(155, 89, 182, 0.08);
}

.platform-btn.active {
  background: #7c3aed;
  border-color: #7c3aed;
  color: white;
  font-weight: 600;
}

.plat-icon { font-size: 14px; }
.plat-name { white-space: nowrap; }

.plat-poster-badge {
  font-size: 9px;
  background: var(--accent-rose, #e75480);
  color: #fff;
  padding: 1px 5px;
  border-radius: 8px;
  font-weight: 700;
}

.gen-only-badge {
  font-size: 9px;
  background: #fef3c7;
  color: #92400e;
  border-radius: 3px;
  padding: 1px 3px;
  margin-left: 2px;
}

/* コピーボタン */
.btn-copy-content {
  width: 100%;
  padding: 12px;
  background: linear-gradient(135deg, rgba(52, 152, 219, 0.1), rgba(155, 89, 182, 0.1));
  border: 1px solid rgba(52, 152, 219, 0.3);
  color: #2980b9;
  border-radius: var(--radius-btn, 12px);
  cursor: pointer;
  font-size: 14px;
  font-weight: 600;
  transition: all 0.3s;
  margin-top: 8px;
}

.btn-copy-content:hover:not(:disabled) {
  background: linear-gradient(135deg, #3498db, #9b59b6);
  color: #fff;
  border-color: transparent;
  transform: translateY(-2px);
  box-shadow: 0 6px 18px rgba(52, 152, 219, 0.3);
}

.btn-copy-content:disabled {
  opacity: 0.45;
  cursor: not-allowed;
}

.submit-area { margin-top: 4px; }

/* AI 画像生成セクション */
.image-gen-section {
  border: 1px solid rgba(155, 89, 182, 0.2);
  border-radius: 12px;
  overflow: hidden;
  margin-bottom: 12px;
  background: rgba(255, 255, 255, 0.5);
}

.image-gen-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 10px 14px;
  cursor: pointer;
  background: linear-gradient(135deg, rgba(155, 89, 182, 0.06), rgba(231, 84, 128, 0.06));
  transition: background 0.2s;
  user-select: none;
}

.image-gen-header:hover {
  background: linear-gradient(135deg, rgba(155, 89, 182, 0.12), rgba(231, 84, 128, 0.12));
}

.image-gen-title {
  font-size: 13px;
  font-weight: 600;
  color: var(--accent-lavender);
}

.powered-by {
  font-size: 10px;
  font-weight: 400;
  color: rgba(155, 89, 182, 0.6);
  margin-left: 6px;
}

.image-gen-toggle {
  font-size: 10px;
  color: rgba(155, 89, 182, 0.5);
}

.image-gen-body {
  padding: 12px 14px;
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.image-prompt-textarea {
  width: 100%;
  background: rgba(255, 255, 255, 0.7);
  border: 1px solid rgba(155, 89, 182, 0.2);
  border-radius: 8px;
  padding: 8px 12px;
  font-size: 13px;
  color: var(--text-primary);
  resize: vertical;
  box-sizing: border-box;
  line-height: 1.5;
}

.image-prompt-textarea:focus {
  outline: none;
  border-color: var(--accent-lavender);
  box-shadow: 0 0 0 3px rgba(155, 89, 182, 0.1);
}

.image-gen-buttons {
  display: flex;
  align-items: center;
  gap: 10px;
}

.btn-gen-image {
  padding: 8px 20px;
  background: linear-gradient(135deg, var(--accent-lavender), var(--accent-rose));
  border: none;
  color: #fff;
  border-radius: 20px;
  cursor: pointer;
  font-size: 13px;
  font-weight: 600;
  transition: all 0.3s;
  white-space: nowrap;
}

.btn-gen-image:hover:not(:disabled) {
  transform: translateY(-2px);
  box-shadow: 0 6px 18px rgba(155, 89, 182, 0.4);
}

.btn-gen-image:disabled {
  opacity: 0.6;
  cursor: not-allowed;
  transform: none;
}

.image-gen-hint {
  font-size: 11px;
  color: rgba(155, 89, 182, 0.6);
  animation: pulse 1.5s infinite;
}

@keyframes pulse {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.5; }
}

.generated-image-preview {
  display: flex;
  gap: 12px;
  align-items: flex-start;
  background: rgba(255, 255, 255, 0.6);
  border: 1px solid rgba(155, 89, 182, 0.15);
  border-radius: 10px;
  padding: 10px;
}

.gen-image-thumb {
  width: 120px;
  height: 120px;
  object-fit: cover;
  border-radius: 8px;
  flex-shrink: 0;
  border: 1px solid rgba(155, 89, 182, 0.2);
}

.gen-image-meta {
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.used-prompt-text {
  font-size: 11px;
  color: rgba(80, 60, 80, 0.5);
  line-height: 1.5;
  max-height: 60px;
  overflow: hidden;
  text-overflow: ellipsis;
}

.gen-image-actions {
  display: flex;
  gap: 8px;
}

.btn-use-image {
  padding: 6px 14px;
  background: linear-gradient(135deg, rgba(155, 89, 182, 0.12), rgba(231, 84, 128, 0.12));
  border: 1px solid var(--accent-lavender);
  color: var(--accent-lavender);
  border-radius: 16px;
  cursor: pointer;
  font-size: 12px;
  font-weight: 600;
  transition: all 0.2s;
}

.btn-use-image:hover {
  background: var(--accent-lavender);
  color: #fff;
}

.btn-regen-image {
  padding: 6px 12px;
  background: transparent;
  border: 1px solid rgba(155, 89, 182, 0.3);
  color: rgba(155, 89, 182, 0.7);
  border-radius: 16px;
  cursor: pointer;
  font-size: 12px;
  transition: all 0.2s;
}

.btn-regen-image:hover:not(:disabled) {
  border-color: var(--accent-lavender);
  color: var(--accent-lavender);
}

.btn-regen-image:disabled {
  opacity: 0.4;
  cursor: not-allowed;
}

/* ── Credential Accordion (UX-3) ── */
.cred-accordion {
  border: 1px solid #e5e7eb;
  border-radius: 10px;
  margin-bottom: 8px;
  overflow: hidden;
}

.cred-header {
  width: 100%;
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 10px 14px;
  background: rgba(255,255,255,0.85);
  border: none;
  cursor: pointer;
  font-size: 13px;
  font-weight: 600;
  color: var(--text-main);
  text-align: left;
  transition: background 0.2s;
}

.cred-header:hover {
  background: rgba(124, 58, 237, 0.05);
}

.cred-arrow {
  margin-left: auto;
  font-size: 11px;
  color: var(--text-sub);
}

.badge-ok {
  font-size: 11px;
  background: #d1fae5;
  color: #065f46;
  border-radius: 4px;
  padding: 1px 6px;
}

.badge-warn {
  font-size: 11px;
  background: #fef3c7;
  color: #92400e;
  border-radius: 4px;
  padding: 1px 6px;
}

.cred-body {
  padding: 12px 14px;
  background: #fafafa;
  border-top: 1px solid #e5e7eb;
}

</style>
