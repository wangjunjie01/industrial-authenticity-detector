const $ = (selector) => document.querySelector(selector);
const draft = $('#draft');
const analyzeButton = $('#analyze');
const count = $('#count');
const statusLine = $('#operation-status');
let updateState = null;

const escapeHtml = (value) => String(value).replace(/[&<>'"]/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;',"'":'&#39;','"':'&quot;'}[c]));
draft.addEventListener('input', () => count.textContent = `${draft.value.length.toLocaleString()} characters`);

async function request(url, options = {}) {
  const response = await fetch(url, options);
  const data = await response.json();
  if (!response.ok) throw new Error(data.error || 'The operation could not be completed.');
  return data;
}

function metric(label, score) {
  return `<div class="metric"><div class="metric-head"><span>${escapeHtml(label)}</span><strong>${score}</strong></div><div class="bar" role="meter" aria-label="${escapeHtml(label)}" aria-valuenow="${score}" aria-valuemin="0" aria-valuemax="100"><b style="width:${score}%"></b></div></div>`;
}

function render(data) {
  $('#empty').classList.add('hidden');
  $('#results').classList.remove('hidden');
  $('#risk').textContent = data.writing_style_risk.ai_like_writing_risk;
  $('#band').textContent = `${data.writing_style_risk.risk_band} style risk`;
  const probability = data.model_detection.probability_percent;
  $('#model-probability').textContent = probability == null ? 'N/A' : probability;
  $('#model-confidence').textContent = `${data.model_detection.confidence} confidence`;
  $('#model-applicability').textContent = data.model_detection.applicability;
  $('#model-id').textContent = `${data.model_detection.model_id} · ${data.model_detection.model_version}`;
  $('#review-guidance').textContent = data.review_guidance.message;
  $('#review-guidance').classList.toggle('conflict', data.review_guidance.signals_conflict);
  $('#authenticity').textContent = data.industrial_authenticity_engine.score;
  $('#predictability').textContent = data.statistical_layer.predictability_proxy;
  $('#finding-count').textContent = data.rule_layer.finding_count;
  const names = {ai_smell_quality:'Formulaicity quality',engineering_credibility:'Engineering credibility',decision_density:'Decision density',specificity:'Specificity',human_voice:'Natural voice',platform_fit:'Platform fit'};
  $('#dimensions').innerHTML = Object.entries(data.industrial_authenticity_engine.dimensions).map(([key,value]) => metric(names[key], value)).join('');
  $('#suggestions').innerHTML = data.revision_plan.map(item => `<li>${escapeHtml(item)}</li>`).join('') || '<li>No priority revision found.</li>';
  $('#sentences').innerHTML = data.sentences.map(item => `<span class="sentence ${item.level}" title="Risk ${item.risk}; rules: ${escapeHtml(item.rules.join(', ') || 'none')}">${escapeHtml(item.text)}</span>`).join('');
  $('#findings').innerHTML = data.rule_layer.findings.map(item => `<div class="finding"><span class="severity ${item.severity}">${escapeHtml(item.severity)}</span><div><p><strong>${escapeHtml(item.snippet)}</strong></p><p>${escapeHtml(item.observation)}</p><small>${escapeHtml(item.action)}</small></div></div>`).join('') || '<p>No material rule-based finding. Review evidence and engineering claims manually before publication.</p>';
}

analyzeButton.addEventListener('click', async () => {
  if (!draft.value.trim()) { draft.focus(); statusLine.textContent = 'Paste a draft before analysis.'; return; }
  analyzeButton.disabled = true; analyzeButton.textContent = 'Analyzing…'; statusLine.textContent = '';
  try {
    const data = await request('/api/analyze', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({text:draft.value, platform:$('#platform').value})});
    render(data); statusLine.textContent = 'Analysis completed locally.';
  } catch (error) { statusLine.textContent = error.message; }
  finally { analyzeButton.disabled = false; analyzeButton.textContent = 'Analyze draft'; }
});

function renderUpdate(data) {
  updateState = data;
  $('#current-version').textContent = `Version ${data.current_version}`;
  $('#update-message').textContent = data.update_available ? `Approved release ${data.available_version} is ready. Installation requires your confirmation.` : (data.last_check_error || 'Up to date. Automatic installation is off.');
  $('#update-button').classList.toggle('hidden', !data.update_available);
  $('#report-link').classList.toggle('hidden', !data.update_available || !data.report_url);
  if (data.report_url) $('#report-link').href = data.report_url;
  $('#rollback-button').classList.toggle('hidden', !data.previous_version);
  const corpus = data.private_corpus;
  $('#corpus-status').textContent = `${corpus.sample_count} local sample${corpus.sample_count === 1 ? '' : 's'}. ${corpus.message}`;
}

async function loadUpdateStatus() {
  try { renderUpdate(await request('/api/update/status')); }
  catch (error) { $('#current-version').textContent = 'Version unavailable'; $('#update-message').textContent = error.message; }
}

$('#update-button').addEventListener('click', async () => {
  if (!updateState?.confirmation_token || !window.confirm(`Install signed detector ${updateState.available_version}? A health check and local acceptance test will run first.`)) return;
  $('#update-button').disabled = true; $('#update-message').textContent = 'Verifying signature, testing, and installing…';
  try { await request('/api/update/apply', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({confirmation_token:updateState.confirmation_token})}); await loadUpdateStatus(); }
  catch (error) { $('#update-message').textContent = error.message; }
  finally { $('#update-button').disabled = false; }
});

$('#rollback-button').addEventListener('click', async () => {
  if (!updateState?.rollback_token || !window.confirm(`Roll back to detector ${updateState.previous_version}?`)) return;
  try { await request('/api/update/rollback', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({confirmation_token:updateState.rollback_token})}); await loadUpdateStatus(); }
  catch (error) { $('#update-message').textContent = error.message; }
});

$('#corpus-import').addEventListener('click', async () => {
  const texts = $('#corpus-text').value.split(/\n\s*\n/).map(text => text.trim()).filter(Boolean);
  if (!texts.length) { $('#corpus-text').focus(); return; }
  $('#corpus-import').disabled = true;
  try {
    const samples = texts.map(text => ({text, category:$('#corpus-category').value}));
    const data = await request('/api/private-corpus/import', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({samples})});
    $('#corpus-text').value = ''; $('#corpus-status').textContent = `${data.sample_count} local samples. ${data.message}`;
  } catch (error) { $('#corpus-status').textContent = error.message; }
  finally { $('#corpus-import').disabled = false; }
});

loadUpdateStatus();
