const $ = (selector) => document.querySelector(selector);
const draft = $('#draft');
const analyzeButton = $('#analyze');
const optimizeButton = $('#optimize');
const count = $('#count');
const statusLine = $('#operation-status');
let updateState = null;
let lastAnalysis = null;
let lastOptimization = null;

const escapeHtml = (value) => String(value).replace(/[&<>'"]/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;',"'":'&#39;','"':'&quot;'}[c]));
const dual = (zh, en) => `${zh} / ${en}`;
const levels = {
  high: dual('高', 'High'),
  medium: dual('中', 'Medium'),
  low: dual('低', 'Low'),
  insufficient: dual('样本不足', 'Insufficient'),
  unavailable: dual('不可用', 'Unavailable'),
};
const dimensionNames = {
  ai_smell_quality: dual('程式化程度质量', 'Formulaicity quality'),
  engineering_credibility: dual('工程可信度', 'Engineering credibility'),
  decision_density: dual('决策信息密度', 'Decision density'),
  specificity: dual('具体性', 'Specificity'),
  human_voice: dual('自然表达', 'Natural voice'),
  platform_fit: dual('平台适配度', 'Platform fit'),
};
const findingTranslations = {
  generic_language: '检测到未与机制、检验方法或结果关联的低信息量表述。',
  unsupported_marketing: '营销主张缺少明确标准或证据来源。',
  templated_transition: '检测到程式化过渡表达。',
  long_sentence: '句子较长且承载了多个观点。',
  repeated_opening: '三个或更多句子使用了相同的开头模式。',
};
const actionTranslations = {
  'Replace the claim with an observable action, constraint, or consequence.': '用可观察的动作、约束或结果替换该表述。',
  'Substantiate the term, qualify it, or remove it.': '为该用语补充证据、限定适用范围，或将其删除。',
  'Use logical adjacency or name the concrete subject instead.': '直接衔接逻辑，或明确写出具体主语。',
  'Split at the decision, condition, or consequence.': '在决策、条件或结果处拆分句子。',
  'Combine related claims or lead with the variable that changes the decision.': '合并相关主张，或先写出会改变决策的变量。',
  'State what should be chosen, under which condition, and why.': '说明应选择什么、适用条件以及原因。',
  'Add only verified constraints, mechanisms, failure modes, or check methods.': '只补充已经核实的约束、机制、失效模式或检验方法。',
  'Name the relevant trade-off instead of presenting benefits without limits.': '明确相关取舍，不要只呈现没有边界的优点。',
};
const bilingualHtml = (zh, en) => `${escapeHtml(zh)}<span class="en-line" lang="en">${escapeHtml(en)}</span>`;
const translatedHtml = (english, chinese) => bilingualHtml(chinese || '请结合原文人工复核。', english);

draft.addEventListener('input', () => count.textContent = `${draft.value.length.toLocaleString()} 字符 / characters`);

async function request(url, options = {}) {
  const response = await fetch(url, options);
  const data = await response.json();
  if (!response.ok) throw new Error(data.error || dual('操作未能完成。', 'The operation could not be completed.'));
  return data;
}

function metric(label, score) {
  return `<div class="metric"><div class="metric-head"><span>${escapeHtml(label)}</span><strong>${score}</strong></div><div class="bar" role="meter" aria-label="${escapeHtml(label)}" aria-valuenow="${score}" aria-valuemin="0" aria-valuemax="100"><b style="width:${score}%"></b></div></div>`;
}

function render(data) {
  lastAnalysis = data;
  $('#empty').classList.add('hidden');
  $('#results').classList.remove('hidden');
  optimizeButton.classList.remove('hidden');
  $('#risk').textContent = data.writing_style_risk.ai_like_writing_risk;
  const riskBand = data.writing_style_risk.risk_band;
  $('#band').textContent = `${levels[riskBand] || riskBand} ${dual('风格风险', 'style risk')}`;
  const probability = data.model_detection.probability_percent;
  $('#model-probability').textContent = probability == null ? 'N/A' : probability;
  const classifications = {
    ai_like_pattern: dual('倾向：更像 AI 类写作模式', 'Tendency: more AI-like pattern'),
    human_like_pattern: dual('倾向：更像人工写作模式', 'Tendency: more human-like pattern'),
    unavailable: dual('倾向：模型不可用', 'Tendency: model unavailable'),
  };
  $('#model-classification').textContent = classifications[data.model_detection.classification] || dual('倾向：需要人工复核', 'Tendency: manual review needed');
  const confidence = data.model_detection.confidence;
  $('#model-confidence').textContent = `${dual('结论置信度', 'Conclusion confidence')}: ${levels[confidence] || dual(confidence, confidence)}`;
  const applicabilityZh = {
    insufficient: '适用性有限：文本过短，概率可能不稳定。',
    low: '部分适用：建议结合人工复核。',
    medium: '在适用范围内，但分数接近校准阈值。',
    high: '适用于校准说明所覆盖的中英文 B2B 类文本。',
    unavailable: '轻量模型无法加载；写作风格分析仍可使用。',
  };
  $('#model-applicability').innerHTML = translatedHtml(data.model_detection.applicability, applicabilityZh[confidence]);
  $('#model-id').textContent = `${data.model_detection.model_id} · ${data.model_detection.model_version}`;
  $('#review-guidance').innerHTML = data.review_guidance.signals_conflict
    ? bilingualHtml('两个独立信号存在差异，请结合高亮证据和上下文人工复核。', 'The two independent signals differ. Review highlighted evidence and context manually.')
    : bilingualHtml('两个轨道仅用于辅助决策，不得作为作者身份的证明。', 'Use both tracks as decision support, never as proof of authorship.');
  $('#review-guidance').classList.toggle('conflict', data.review_guidance.signals_conflict);
  $('#authenticity').textContent = data.industrial_authenticity_engine.score;
  $('#predictability').textContent = data.statistical_layer.predictability_proxy;
  $('#finding-count').textContent = data.rule_layer.finding_count;
  $('#dimensions').innerHTML = Object.entries(data.industrial_authenticity_engine.dimensions).map(([key,value]) => metric(dimensionNames[key] || key, value)).join('');
  $('#suggestions').innerHTML = data.revision_plan.map(item => `<li>${translatedHtml(item, actionTranslations[item])}</li>`).join('') || `<li>${bilingualHtml('未发现需要优先修改的内容。', 'No priority revision found.')}</li>`;
  $('#sentences').innerHTML = data.sentences.map(item => `<span class="sentence ${item.level}" title="风险 / Risk ${item.risk}; 规则 / rules: ${escapeHtml(item.rules.join(', ') || dual('无', 'none'))}">${escapeHtml(item.text)}</span>`).join('');
  $('#findings').innerHTML = data.rule_layer.findings.map(item => `<div class="finding"><span class="severity ${item.severity}">${escapeHtml(levels[item.severity] || item.severity)}</span><div><p><strong>${escapeHtml(item.snippet)}</strong></p><p>${translatedHtml(item.observation, findingTranslations[item.rule])}</p><small>${translatedHtml(item.action, actionTranslations[item.action])}</small></div></div>`).join('') || `<p>${bilingualHtml('未发现明显的规则问题。发布前仍应人工复核证据和工程主张。', 'No material rule-based finding. Review evidence and engineering claims manually before publication.')}</p>`;
}

async function analyzeDraft() {
  if (!draft.value.trim()) { draft.focus(); statusLine.textContent = dual('请先粘贴文案再分析。', 'Paste a draft before analysis.'); return; }
  analyzeButton.disabled = true; analyzeButton.textContent = dual('分析中…', 'Analyzing…'); statusLine.textContent = '';
  try {
    const data = await request('/api/analyze', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({text:draft.value, platform:$('#platform').value})});
    render(data); statusLine.textContent = dual('已在本机完成分析。', 'Analysis completed locally.');
  } catch (error) { statusLine.textContent = error.message; }
  finally { analyzeButton.disabled = false; analyzeButton.textContent = dual('分析文案', 'Analyze draft'); }
}

analyzeButton.addEventListener('click', analyzeDraft);

const factFields = [
  'audience_decision', 'application', 'specifications_constraints',
  'failure_risk_check', 'evidence', 'tradeoff_preference', 'cta',
];

function collectFacts() {
  return Object.fromEntries(factFields.map(key => [key, $(`#fact-${key}`).value.trim()]).filter(([, value]) => value));
}

function scoreChangeRow(label, item, kind = 'quality') {
  const improvement = kind === 'risk' ? item.before - item.after : item.after - item.before;
  const className = improvement > 0 ? 'better' : improvement < 0 ? 'worse' : 'same';
  const change = improvement > 0 ? `+${improvement}` : `${improvement}`;
  const direction = kind === 'risk' ? dual('越低越好', 'lower is better') : dual('越高越好', 'higher is better');
  const changeLabel = improvement === 0
    ? dual('无变化', 'no change')
    : `${improvement > 0 ? dual('改善', 'improvement') : dual('退步', 'regression')} ${change}`;
  return `<div class="score-change ${className}"><span>${escapeHtml(label)}<small>${direction}</small></span><strong>${item.before} → ${item.after}<small>${changeLabel}</small></strong></div>`;
}

function renderOptimization(data, sourceText) {
  lastOptimization = data;
  $('#optimization-result').classList.remove('hidden');
  $('#original-preview').textContent = sourceText;
  $('#optimized-preview').textContent = data.optimized_text;
  const statusMessages = {
    improved: dual('已生成通过事实保护和质量门槛的优化稿。', 'Generated an optimized draft that passed fact protection and quality gates.'),
    blocked_by_missing_facts: dual('缺少已核实的工程事实，当前没有可安全通过门槛的优化稿。', 'Verified engineering facts are missing, so no candidate safely passed the quality gates.'),
    no_safe_improvement: dual('未找到可在不改变原意的前提下安全提高总分的版本。', 'No version safely improved the total score without changing the meaning.'),
  };
  $('#optimization-status').textContent = statusMessages[data.status] || data.status;

  const quality = data.score_changes.quality;
  const qualityRows = [scoreChangeRow(dual('工业真实性', 'Industrial authenticity'), quality.industrial_authenticity)];
  Object.entries(quality).filter(([key]) => key !== 'industrial_authenticity').forEach(([key, value]) => qualityRows.push(scoreChangeRow(dimensionNames[key] || key, value)));
  Object.entries(data.score_changes.risks).forEach(([key, value]) => {
    const name = key === 'writing_style_risk' ? dual('写作风格风险', 'Writing style risk') : dual('可预测性代理指标', 'Predictability proxy');
    qualityRows.push(scoreChangeRow(name, value, 'risk'));
  });
  $('#optimization-scores').innerHTML = qualityRows.join('');

  $('#optimization-changes').innerHTML = data.change_log.length
    ? data.change_log.map(item => `<div class="change-item"><strong>${escapeHtml(item.reason_zh)}</strong><span class="en-line" lang="en">${escapeHtml(item.reason_en)}</span></div>`).join('')
    : `<p>${bilingualHtml('未应用任何修改。', 'No changes were applied.')}</p>`;
  $('#optimization-gaps').innerHTML = data.unresolved_fact_requests.length
    ? `<ul>${data.unresolved_fact_requests.map(item => `<li>${bilingualHtml(item.message_zh, item.message_en)}</li>`).join('')}</ul>`
    : `<p>${bilingualHtml('没有检测到阻塞性事实缺口。', 'No blocking fact gap was detected.')}</p>`;

  const modelChange = data.score_changes.model_detection;
  const probability = modelChange.before == null || modelChange.after == null
    ? dual('模型概率不可用。', 'Model probability is unavailable.')
    : `${dual('AI 类模式概率仅供参考', 'AI-like pattern probability is reference only')}: ${modelChange.before}% → ${modelChange.after}%`;
  const selectionNote = modelChange.used_for_selection === false
    ? bilingualHtml('此概率没有参与优化候选的选择或通过门槛。', 'This probability was not used to select or accept the optimized candidate.')
    : '';
  $('#optimization-model-note').innerHTML = `${escapeHtml(probability)}${bilingualHtml(data.model_detection_note.zh, data.model_detection_note.en)}${selectionNote}`;
  const canApply = data.status === 'improved' && data.safety.passed && data.optimized_text !== sourceText;
  $('#apply-optimization').disabled = !canApply;
  $('#copy-optimization').disabled = !canApply;
  $('#copy-status').textContent = '';
}

async function generateOptimization() {
  const sourceText = draft.value;
  if (!sourceText.trim()) { draft.focus(); return; }
  const button = $('#generate-optimization');
  button.disabled = true;
  button.textContent = dual('安全检查与优化中…', 'Checking and optimizing safely…');
  try {
    const data = await request('/api/optimize', {
      method: 'POST', headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({
        text: sourceText,
        platform: $('#platform').value,
        verified_facts: collectFacts(),
        confirmed_verified: $('#facts-confirmed').checked,
      }),
    });
    renderOptimization(data, sourceText);
  } catch (error) {
    $('#optimization-result').classList.remove('hidden');
    $('#optimization-status').textContent = error.message;
  } finally {
    button.disabled = false;
    button.textContent = dual('生成安全优化稿', 'Generate safe optimization');
  }
}

optimizeButton.addEventListener('click', () => {
  $('#optimize-workspace').classList.remove('hidden');
  $('#optimize-workspace').scrollIntoView({behavior: 'smooth', block: 'start'});
  if (!lastOptimization) generateOptimization();
});

$('#fact-form').addEventListener('submit', event => { event.preventDefault(); generateOptimization(); });
$('#regenerate-optimization').addEventListener('click', generateOptimization);
$('#discard-optimization').addEventListener('click', () => {
  lastOptimization = null;
  $('#optimization-result').classList.add('hidden');
  $('#optimize-workspace').classList.add('hidden');
});
$('#facts-confirmed').addEventListener('change', event => {
  $('#fact-confirmation-note').textContent = event.target.checked
    ? dual('已确认的信息可以用于优化；提交后仍会运行事实保护检查。', 'Confirmed information may be used; fact-protection checks still run before acceptance.')
    : dual('未确认的信息只作为待核实备注，不会写入优化稿。', 'Unconfirmed information remains a note and will not enter the optimized draft.');
});
$('#copy-optimization').addEventListener('click', async () => {
  if (!lastOptimization?.optimized_text) return;
  try {
    await navigator.clipboard.writeText(lastOptimization.optimized_text);
    $('#copy-status').textContent = dual('优化稿已复制。', 'Optimized draft copied.');
  } catch (_) {
    $('#copy-status').textContent = dual('浏览器未允许复制，请手动选择优化稿。', 'Copy permission was denied; select the optimized draft manually.');
  }
});
$('#apply-optimization').addEventListener('click', async () => {
  if (!lastOptimization || !lastOptimization.safety.passed || lastOptimization.status !== 'improved') return;
  draft.value = lastOptimization.optimized_text;
  draft.dispatchEvent(new Event('input'));
  $('#optimize-workspace').classList.add('hidden');
  lastOptimization = null;
  await analyzeDraft();
  $('#results').scrollIntoView({behavior: 'smooth', block: 'start'});
});

function renderUpdate(data) {
  updateState = data;
  $('#current-version').textContent = `应用 / App ${data.app_version} · 检测模型 / Detector ${data.current_version}`;
  $('#update-message').textContent = data.update_available
    ? `已批准版本 ${data.available_version} 可用，安装前需要您的确认。 / Approved release ${data.available_version} is ready. Installation requires your confirmation.`
    : (data.last_check_error
      ? `${dual('更新检查失败', 'Update check failed')}: ${data.last_check_error}`
      : (data.release_status === 'no_release'
        ? dual('当前没有已批准的新版本，自动安装已关闭。', 'No approved update is currently published. Automatic installation is off.')
        : dual('已是最新版本，自动安装已关闭。', 'Up to date. Automatic installation is off.')));
  $('#update-button').classList.toggle('hidden', !data.update_available);
  $('#report-link').classList.toggle('hidden', !data.update_available || !data.report_url);
  if (data.report_url) $('#report-link').href = data.report_url;
  $('#rollback-button').classList.toggle('hidden', !data.previous_version);
  const corpus = data.private_corpus;
  const corpusMessage = corpus.sufficient
    ? dual('本地行业验证已就绪。', 'Local industry validation is ready.')
    : dual('行业本地验证样本不足，建议至少 20 个。', 'Industry local validation samples are insufficient; 20 or more are recommended.');
  $('#corpus-status').textContent = `${corpus.sample_count} ${dual('个本地样本', `local sample${corpus.sample_count === 1 ? '' : 's'}`)}。 ${corpusMessage}`;
}

async function loadUpdateStatus() {
  try { renderUpdate(await request('/api/update/status')); }
  catch (error) { $('#current-version').textContent = dual('版本不可用', 'Version unavailable'); $('#update-message').textContent = error.message; }
}

$('#update-button').addEventListener('click', async () => {
  if (!updateState?.confirmation_token || !window.confirm(`安装已签名的检测器 ${updateState.available_version}？系统会先运行健康检查和本地验收。\n\nInstall signed detector ${updateState.available_version}? A health check and local acceptance test will run first.`)) return;
  $('#update-button').disabled = true; $('#update-message').textContent = dual('正在验证签名、测试并安装…', 'Verifying signature, testing, and installing…');
  try { await request('/api/update/apply', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({confirmation_token:updateState.confirmation_token})}); await loadUpdateStatus(); }
  catch (error) { $('#update-message').textContent = error.message; }
  finally { $('#update-button').disabled = false; }
});

$('#rollback-button').addEventListener('click', async () => {
  if (!updateState?.rollback_token || !window.confirm(`回滚到检测器 ${updateState.previous_version}？\n\nRoll back to detector ${updateState.previous_version}?`)) return;
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
    const importedMessage = data.sufficient
      ? dual('本地行业验证已就绪。', 'Local industry validation is ready.')
      : dual('行业本地验证样本不足，建议至少 20 个。', 'Industry local validation samples are insufficient; 20 or more are recommended.');
    $('#corpus-text').value = ''; $('#corpus-status').textContent = `${data.sample_count} ${dual('个本地样本', 'local samples')}。 ${importedMessage}`;
  } catch (error) { $('#corpus-status').textContent = error.message; }
  finally { $('#corpus-import').disabled = false; }
});

loadUpdateStatus();
