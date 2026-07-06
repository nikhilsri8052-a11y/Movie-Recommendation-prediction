// ── Dark Mode ──────────────────────────────────────────────
const html = document.documentElement;
const themeToggle = document.getElementById('themeToggle');

function applyTheme(theme) {
    html.setAttribute('data-theme', theme);
    document.documentElement.style.colorScheme = theme === 'dark' ? 'dark' : 'light';
    localStorage.setItem('theme', theme);
    updateThemeButton();
}

function updateThemeButton() {
    if (!themeToggle) return;
    const isDark = html.getAttribute('data-theme') === 'dark';
    themeToggle.innerHTML = `<span class="me-2">${isDark ? '☽' : '☀'}</span><span>${isDark ? 'Dark' : 'Light'}</span>`;
}

const saved = localStorage.getItem('theme');
const prefersDark = window.matchMedia('(prefers-color-scheme: dark)').matches;
const initialTheme = saved || (prefersDark ? 'dark' : 'light');
applyTheme(initialTheme);

if (themeToggle) {
    themeToggle.addEventListener('click', () => {
        const next = html.getAttribute('data-theme') === 'dark' ? 'light' : 'dark';
        applyTheme(next);
    });
}

// ── Sliders ──────────────────────────────────────────────────
function updateSlider(input, fill, display, formatter) {
    const min = parseFloat(input.min);
    const max = parseFloat(input.max);
    const val = parseFloat(input.value);
    const pct = ((val - min) / (max - min)) * 100;
    fill.style.width = pct + '%';
    if (display) display.textContent = formatter(val);
}

const sliderConfigs = [
    { id: 'runtime', formatter: v => v + ' min' },
    { id: 'minRating', formatter: v => v.toFixed(1) },
    { id: 'popularity', formatter: v => v.toFixed(0) },
    { id: 'minVotes', formatter: v => v.toLocaleString() },
];

const sliders = {};
sliderConfigs.forEach(cfg => {
    const input = document.getElementById(cfg.id);
    if (!input) return;
    const fill = document.getElementById(cfg.id + 'Fill');
    const display = document.getElementById(cfg.id + 'Display');
    sliders[cfg.id] = { input, fill, display, formatter: cfg.formatter };
    updateSlider(input, fill, display, cfg.formatter);
    input.addEventListener('input', () => {
        updateSlider(input, fill, display, cfg.formatter);
        syncSummary();
    });
});

// ── Summary box ──────────────────────────────────────────────
const summaryGenre = document.getElementById('summaryGenre');
const summaryLanguage = document.getElementById('summaryLanguage');
const summaryRuntime = document.getElementById('summaryRuntime');
const summaryRating = document.getElementById('summaryRating');

function syncSummary() {
    if (summaryGenre) {
        const genreSelect = document.getElementById('genre');
        summaryGenre.textContent = genreSelect && genreSelect.value ? genreSelect.value : 'Any';
    }
    if (summaryLanguage) {
        const languageSelect = document.getElementById('language');
        const labelMap = {
            '': 'Any',
            en: 'English',
            fr: 'French',
            de: 'German',
            es: 'Spanish',
            hi: 'Hindi',
            ja: 'Japanese',
            ko: 'Korean',
            cn: 'Mandarin'
        };
        summaryLanguage.textContent = labelMap[languageSelect?.value] || 'Any';
    }
    if (summaryRuntime && sliders.runtime) summaryRuntime.textContent = sliders.runtime.input.value + ' min';
    if (summaryRating && sliders.minRating) summaryRating.textContent = sliders.minRating.input.value + '/10';
}

['genre', 'language'].forEach(id => {
    const el = document.getElementById(id);
    if (el) el.addEventListener('change', syncSummary);
});
syncSummary();

// ── Gauge ────────────────────────────────────────────────────
function animateGauge(percent) {
    const needle = document.getElementById('gaugeNeedle');
    const gaugeArc = document.getElementById('gaugeArc');
    const ARC_LEN = 377;
    const ARC_START = -90;
    const ARC_SWEEP = 180;
    const clamp = (v, lo, hi) => Math.max(lo, Math.min(hi, v));
    const pct = clamp(percent / 100, 0, 1);
    const needleAngle = ARC_START + pct * ARC_SWEEP;
    const dashOffset = ARC_LEN - pct * ARC_LEN;
    needle.style.transform = `rotate(${needleAngle}deg)`;
    gaugeArc.style.strokeDashoffset = dashOffset;
}

function animateCounter(el, target, duration = 1200) {
    let start = null;
    const step = ts => {
        if (!start) start = ts;
        const prog = Math.min((ts - start) / duration, 1);
        const eased = 1 - Math.pow(1 - prog, 3);
        el.textContent = (target * eased).toFixed(1) + '%';
        if (prog < 1) requestAnimationFrame(step);
    };
    requestAnimationFrame(step);
}

// ── Result rendering ───────────────────────────────────────────
const resultSection = document.getElementById('resultSection');
const resultErrorWrap = document.getElementById('resultErrorWrap');
const resultError = document.getElementById('resultError');
const riskBadge = document.getElementById('riskBadge');

function showSuccess(data) {
    if (!resultSection) return;

    if (resultErrorWrap) resultErrorWrap.style.display = 'none';

    resultSection.classList.remove('visible');
    void resultSection.offsetWidth;
    resultSection.classList.add('visible');

    const readingEl = document.getElementById('readingValue');
    const labelEl = document.getElementById('predictionLabel');
    const summaryEl = document.getElementById('predictionSummary');
    const detailsEl = document.getElementById('movieDetails');
    const listEl = document.getElementById('recommendationList');

    animateCounter(readingEl, data.match_percentage);
    animateGauge(data.match_percentage);

    const message = data.prediction_text || data.message || 'Recommendation complete';
    if (labelEl) labelEl.textContent = data.movie_title ? 'Closest match from the notebook-style recommender' : 'Based on the values you entered';
    if (summaryEl) summaryEl.textContent = message;
    if (detailsEl) detailsEl.textContent = data.movie_details || 'A tailored suggestion from the movie catalog.';

    if (listEl) {
        const recommendations = Array.isArray(data.recommendations) ? data.recommendations : [];
        if (recommendations.length) {
            listEl.innerHTML = recommendations.slice(0, 6).map((movie, index) => `
                <li class="list-group-item px-0 py-2">
                    <div class="d-flex justify-content-between align-items-start gap-3">
                        <div>
                            <div class="fw-semibold">${index + 1}. ${movie.title}</div>
                            <div class="small text-muted">${movie.details}</div>
                        </div>
                        <span class="badge rounded-pill text-bg-light">${movie.score.toFixed(2)}</span>
                    </div>
                </li>
            `).join('');
        } else {
            listEl.innerHTML = '';
        }
    }

    if (riskBadge) {
        const isHigh = (data.match_level || '').toLowerCase().includes('high');
        riskBadge.textContent = data.match_level || '—';
        riskBadge.className = 'badge rounded-pill ' + (isHigh ? 'text-bg-success' : 'text-bg-warning');
    }

    resultSection.scrollIntoView({ behavior: 'smooth', block: 'start' });
}

function showError(message) {
    if (!resultSection || !resultErrorWrap || !resultError) return;

    resultErrorWrap.style.display = '';
    resultError.textContent = 'Error: ' + message;

    resultSection.classList.remove('visible');
    void resultSection.offsetWidth;
    resultSection.classList.add('visible');

    resultSection.scrollIntoView({ behavior: 'smooth', block: 'start' });
}

// ── Form submission ──────────────────────────────────────────
const form = document.getElementById('predictForm');
const btn = document.getElementById('predictBtn');

if (form && btn) {
    form.addEventListener('submit', async (e) => {
        e.preventDefault();
        btn.disabled = true;
        btn.querySelector('.btn-text').textContent = 'Finding…';
        const payload = new FormData(form);
        try {
            const res = await fetch('/predict', {
                method: 'POST',
                body: payload,
                headers: { 'X-Requested-With': 'XMLHttpRequest' }
            });
            const data = await res.json();
            if (data.success) {
                showSuccess(data);
            } else {
                showError(data.error || 'Something went wrong.');
            }
        } catch (err) {
            showError('Could not reach the server. Make sure Flask is running.');
        } finally {
            btn.disabled = false;
            btn.querySelector('.btn-text').textContent = 'Find My Movie';
        }
    });
}

// ── Render server-side result on full page load (non-AJAX fallback) ──
window.addEventListener('DOMContentLoaded', () => {
    if (window.FLASK_RESULT) {
        if (window.FLASK_RESULT.success) {
            showSuccess(window.FLASK_RESULT);
        } else {
            showError(window.FLASK_RESULT.error || 'Something went wrong.');
        }
    }
});