const $ = (selector) => document.querySelector(selector);
const draft = $('#draft');
const analyzeButton = $('#analyze');
const count = $('#count');
const statusLine = $('#operation-status');
let updateState = null;

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
  $('#empty').classList.add('hidden');
  $('#results').classList.remove('hidden');
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

analyzeButton.addEventListener('click', async () => {
  if (!draft.value.trim()) { draft.focus(); statusLine.textContent = dual('请先粘贴文案再分析。', 'Paste a draft before analysis.'); return; }
  analyzeButton.disabled = true; analyzeButton.textContent = dual('分析中…', 'Analyzing…'); statusLine.textContent = '';
  try {
    const data = await request('/api/analyze', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({text:draft.value, platform:$('#platform').value})});
    render(data); statusLine.textContent = dual('已在本机完成分析。', 'Analysis completed locally.');
  } catch (error) { statusLine.textContent = error.message; }
  finally { analyzeButton.disabled = false; analyzeButton.textContent = dual('分析文案', 'Analyze draft'); }
});

function renderUpdate(data) {
  updateState = data;
  $('#current-version').textContent = `${dual('版本', 'Version')} ${data.current_version}`;
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
