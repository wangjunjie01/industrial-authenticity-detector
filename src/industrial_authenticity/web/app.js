const draft = document.querySelector('#draft');
const button = document.querySelector('#analyze');
const count = document.querySelector('#count');
const escapeHtml = (value) => String(value).replace(/[&<>'"]/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;',"'":'&#39;','"':'&quot;'}[c]));
draft.addEventListener('input', () => count.textContent = `${draft.value.length.toLocaleString()} characters`);

function metric(label, score) {
  return `<div class="metric"><div class="metric-head"><span>${escapeHtml(label)}</span><strong>${score}</strong></div><div class="bar"><b style="width:${score}%"></b></div></div>`;
}

function render(data) {
  document.querySelector('#empty').classList.add('hidden');
  document.querySelector('#results').classList.remove('hidden');
  document.querySelector('#risk').textContent = data.classifier.ai_like_writing_risk;
  document.querySelector('#band').textContent = `${data.classifier.risk_band} risk`;
  document.querySelector('#authenticity').textContent = data.industrial_authenticity_engine.score;
  document.querySelector('#predictability').textContent = data.statistical_layer.predictability_proxy;
  const names = {ai_smell_quality:'AI smell quality',engineering_credibility:'Engineering credibility',decision_density:'Decision density',specificity:'Specificity',human_voice:'Human voice',platform_fit:'Platform fit'};
  document.querySelector('#dimensions').innerHTML = Object.entries(data.industrial_authenticity_engine.dimensions).map(([key,value]) => metric(names[key], value)).join('');
  document.querySelector('#suggestions').innerHTML = data.revision_plan.map(item => `<li>${escapeHtml(item)}</li>`).join('') || '<li>No priority revision found.</li>';
  document.querySelector('#sentences').innerHTML = data.sentences.map(item => `<span class="sentence ${item.level}" title="Risk ${item.risk}; rules: ${escapeHtml(item.rules.join(', ') || 'none')}">${escapeHtml(item.text)}</span>`).join('');
  document.querySelector('#findings').innerHTML = data.rule_layer.findings.map(item => `<div class="finding"><span class="severity ${item.severity}">${escapeHtml(item.severity)}</span><div><p><strong>${escapeHtml(item.snippet)}</strong></p><p>${escapeHtml(item.observation)}</p><small>${escapeHtml(item.action)}</small></div></div>`).join('') || '<p>No material rule-based finding. Review evidence and engineering claims manually before publication.</p>';
}

button.addEventListener('click', async () => {
  if (!draft.value.trim()) { draft.focus(); return; }
  button.disabled = true; button.textContent = 'Analyzing…';
  try {
    const response = await fetch('/api/analyze', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({text:draft.value, platform:document.querySelector('#platform').value})});
    const data = await response.json();
    if (!response.ok) throw new Error(data.error || 'Analysis failed');
    render(data);
  } catch (error) { window.alert(error.message); }
  finally { button.disabled = false; button.textContent = 'Analyze draft'; }
});

