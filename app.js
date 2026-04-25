const topics = [
  { key: 'math_science', name: '수학/과학', desc: '패턴·원리·실험 사고' },
  { key: 'history_humanities', name: '역사/인문', desc: '시대·사람·문화 이해' },
  { key: 'philosophy_ethics', name: '철학/윤리', desc: '공정함·선택·책임 탐구' },
  { key: 'literature', name: '문학', desc: '이야기·감정·상상 확장' }
];

const modes = ['Depth', 'Breadth'];
const liveModes = ['Read with me', 'Talk with me', 'Ask me questions', 'Help me write', 'Let’s remember together'];

const state = {
  topic: topics[0].key,
  mode: 'Depth',
  live: 'Read with me',
  token: null,
  user: null,
  modelProvider: 'unknown'
};

async function api(path, method = 'GET', body = null) {
  const headers = { 'Content-Type': 'application/json' };
  if (state.token) headers['Authorization'] = `Bearer ${state.token}`;
  const res = await fetch(path, {
    method,
    headers,
    body: body ? JSON.stringify(body) : null
  });
  const data = await res.json();
  if (!res.ok) throw new Error(data.error || 'request_failed');
  return data;
}

function createButton(text, className, onClick) {
  const btn = document.createElement('button');
  btn.textContent = text;
  btn.className = className;
  btn.onclick = onClick;
  return btn;
}

function renderStartSelectors() {
  const topicButtonsEl = document.getElementById('topic-buttons');
  const modeButtonsEl = document.getElementById('mode-buttons');
  const liveButtonsEl = document.getElementById('live-buttons');

  topicButtonsEl.innerHTML = '';
  topics.forEach((topic) => {
    const btn = document.createElement('button');
    btn.className = `topic-btn ${state.topic === topic.key ? 'selected' : ''}`;
    btn.innerHTML = `<b>${topic.name}</b><span>${topic.desc}</span>`;
    btn.onclick = () => {
      state.topic = topic.key;
      renderStartSelectors();
    };
    topicButtonsEl.appendChild(btn);
  });

  modeButtonsEl.innerHTML = '';
  modes.forEach((mode) => {
    modeButtonsEl.appendChild(createButton(mode, `pill ${state.mode === mode ? 'selected' : ''}`, () => {
      state.mode = mode;
      renderStartSelectors();
    }));
  });

  liveButtonsEl.innerHTML = '';
  liveModes.forEach((live) => {
    liveButtonsEl.appendChild(createButton(live, `pill ${state.live === live ? 'selected' : ''}`, () => {
      state.live = live;
      renderStartSelectors();
    }));
  });
}

async function login() {
  const name = document.getElementById('name-input').value.trim();
  const status = document.getElementById('login-status');
  if (name.length < 2) {
    status.textContent = '이름을 2글자 이상 입력해주세요.';
    return;
  }

  try {
    const modelInfo = await api('/api/models');
    state.modelProvider = `${modelInfo.provider} / ${modelInfo.models.join(', ')}`;

    const result = await api('/api/login', 'POST', { name });
    state.token = result.token;
    state.user = result.user;

    status.textContent = `환영해요, ${state.user.name}! (${state.modelProvider})`;
    document.getElementById('login-card').classList.add('hidden');
    document.getElementById('start-card').classList.remove('hidden');
    renderStartSelectors();
  } catch (err) {
    status.textContent = `로그인 실패: ${err.message}`;
  }
}

function renderLesson(payload) {
  const lessonTitle = document.getElementById('lesson-title');
  const modelBadge = document.getElementById('model-badge');
  const content = document.getElementById('lesson-content');

  lessonTitle.textContent = `${payload.topic} | ${payload.mode} | ${payload.live_mode}`;
  modelBadge.textContent = `생성 엔진: ${payload.source || state.modelProvider}`;

  content.innerHTML = `
    <div class="block"><h3>이 주제가 맞는 이유</h3><p>${payload.reason}</p></div>
    <div class="block"><h3>진짜 책 추천</h3>
      <ul class="list-tight">
        <li>${payload.books[0].step} | ${payload.books[0].title} (${payload.books[0].lang})</li>
        <li>${payload.books[1].step} | ${payload.books[1].title} (${payload.books[1].lang})</li>
      </ul>
    </div>
    <div class="block"><h3>영어 읽기 자료: ${payload.reading.title}</h3>
      <ol class="list-tight">${payload.reading.text.map(t => `<li>${t}</li>`).join('')}</ol>
      <p><b>쉬운 한국어 요약:</b> ${payload.reading.summary_ko}</p>
    </div>
    <div class="block"><h3>핵심 단어 5개</h3>
      <div class="chips">${payload.reading.keywords.map(w => `<span class="chip">${w}</span>`).join('')}</div>
    </div>
    <div class="block"><h3>이해 질문</h3><ol class="list-tight">${payload.understanding_questions.map(q => `<li>${q}</li>`).join('')}</ol></div>
    <div class="block"><h3>영어 대화 질문</h3><ol class="list-tight">${payload.conversation_questions.map(q => `<li>${q}</li>`).join('')}</ol></div>
    <div class="block"><h3>부모/교사 질문</h3><ol class="list-tight">${payload.parent_questions.map(q => `<li>${q}</li>`).join('')}</ol></div>
    <div class="block"><h3>작업기억 강화 미션</h3><p>${payload.working_memory}</p></div>
    <div class="block"><h3>글쓰기 활동</h3>
      <p><b>Topic:</b> ${payload.writing.topic}</p>
      <p><b>Big Question:</b> ${payload.writing.big_question}</p>
      <p><b>Sentence Starters:</b> ${payload.writing.starters.join(' / ')}</p>
    </div>
  `;

  renderWorksheet(payload);

  document.getElementById('start-card').classList.add('hidden');
  document.getElementById('lesson-card').classList.remove('hidden');
  document.getElementById('worksheet-card').classList.remove('hidden');
}

function renderWorksheet(payload) {
  document.getElementById('worksheet-preview').innerHTML = `
    <h3>${payload.topic} Worksheet (${payload.mode})</h3>
    <p><b>Big Question:</b> ${payload.writing.big_question}</p>
    <hr/>
    <p><b>Reading:</b> ${payload.reading.text.join(' ')}</p>
    <p><b>Keywords:</b> ${payload.reading.keywords.join(', ')}</p>
    <p><b>Comprehension:</b> ${payload.understanding_questions.join(' | ')}</p>
    <p><b>Conversation:</b> ${payload.conversation_questions.join(' | ')}</p>
    <p><b>Parent/Teacher:</b> ${payload.parent_questions.join(' | ')}</p>
    <p><b>Working Memory:</b> ${payload.working_memory}</p>
    <p>${payload.worksheet_note}</p>
  `;
}

async function generateTask() {
  try {
    const payload = await api('/api/generate-task', 'POST', {
      topic: state.topic,
      mode: state.mode,
      live_mode: state.live
    });
    renderLesson(payload);
  } catch (err) {
    alert(`과제 생성 실패: ${err.message}`);
  }
}

function setupActions() {
  document.getElementById('login-btn').onclick = login;
  document.getElementById('start-learning').onclick = generateTask;

  document.getElementById('back-home').onclick = () => {
    document.getElementById('lesson-card').classList.add('hidden');
    document.getElementById('worksheet-card').classList.add('hidden');
    document.getElementById('start-card').classList.remove('hidden');
    renderStartSelectors();
  };

  document.getElementById('save-pdf').onclick = () => window.print();
  document.getElementById('print-view').onclick = () => window.print();
}

setupActions();
