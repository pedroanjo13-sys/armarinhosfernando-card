let APP_STATE = null;
let CURRENT_TAB = 'dashboard';
let STATEMENT_FILTER = 'all';
let CURRENT_ADMIN_USER = null;

function maskAdminCpfInput(el) {
  let v = (el.value || '').replace(/\D/g, '').slice(0, 11);
  if (v.length > 9) v = v.replace(/(\d{3})(\d{3})(\d{3})(\d{1,2})/, '$1.$2.$3-$4');
  else if (v.length > 6) v = v.replace(/(\d{3})(\d{3})(\d{1,3})/, '$1.$2.$3');
  else if (v.length > 3) v = v.replace(/(\d{3})(\d{1,3})/, '$1.$2');
  el.value = v;
}

function getAllowedTabsForRole(role) {
  if (role === 'credito') return ['leads'];
  if (role === 'cobranca') return ['statements', 'rules', 'simulator'];
  return ['dashboard', 'leads', 'pos', 'statements', 'rules', 'simulator', 'roi', 'team', 'environments', 'settings'];
}

function applyAdminRolePermissions(adminUser) {
  CURRENT_ADMIN_USER = adminUser;
  const role = adminUser?.role || 'adm_geral';
  const allowed = getAllowedTabsForRole(role);

  const badgeMap = {
    adm_geral: '🛡️ ADM GERAL (ACESSO TOTAL)',
    credito: '💳 NICHO RESTRITO: CRÉDITO',
    cobranca: '📞 NICHO RESTRITO: COBRANÇA'
  };
  const sbBadge = document.getElementById('sidebar-role-badge');
  const sbName = document.getElementById('sidebar-user-name');
  const sbCpf = document.getElementById('sidebar-user-cpf');
  const topPill = document.getElementById('topbar-role-pill');

  if (sbBadge) sbBadge.textContent = badgeMap[role] || role;
  if (sbName) sbName.textContent = adminUser?.full_name || 'Administrador';
  if (sbCpf) sbCpf.textContent = `CPF: ${adminUser?.cpf || ''} • ${adminUser?.branch || 'Matriz'}`;
  if (topPill) topPill.textContent = badgeMap[role] || role;

  const allTabs = ['dashboard', 'leads', 'pos', 'statements', 'rules', 'simulator', 'roi', 'team', 'environments', 'settings'];
  allTabs.forEach(t => {
    const li = document.getElementById(`nav-item-${t}`);
    if (li) li.style.display = allowed.includes(t) ? 'block' : 'none';
  });

  const secLoja = document.getElementById('nav-sec-loja');
  const secCob = document.getElementById('nav-sec-cobranca');
  const secAdm = document.getElementById('nav-sec-admin');
  if (secLoja) secLoja.style.display = (role === 'adm_geral' || role === 'credito') ? 'block' : 'none';
  if (secCob) secCob.style.display = (role === 'adm_geral' || role === 'cobranca') ? 'block' : 'none';
  if (secAdm) secAdm.style.display = (role === 'adm_geral') ? 'block' : 'none';

  const topTeam = document.getElementById('top-btn-team');
  const topEnv = document.getElementById('top-btn-env');
  const topCad = document.getElementById('top-link-cadastro');
  const topPos = document.getElementById('top-link-webpos');

  if (topTeam) topTeam.style.display = role === 'adm_geral' ? 'inline-flex' : 'none';
  if (topEnv) topEnv.style.display = role === 'adm_geral' ? 'inline-flex' : 'none';
  if (topCad) topCad.style.display = (role === 'adm_geral' || role === 'credito') ? 'inline-flex' : 'none';
  if (topPos) topPos.style.display = role === 'adm_geral' ? 'inline-flex' : 'none';

  if (!allowed.includes(CURRENT_TAB)) {
    switchTab(allowed[0]);
  } else {
    switchTab(CURRENT_TAB);
  }
}

function formatBRL(val) {
  const num = Number(val || 0);
  return num.toLocaleString('pt-BR', { style: 'currency', currency: 'BRL' });
}

function formatDateBR(dateStr) {
  if (!dateStr) return '—';
  const parts = dateStr.split(' ')[0].split('-');
  if (parts.length !== 3) return dateStr;
  return `${parts[2]}/${parts[1]}/${parts[0]}`;
}

function showToast(msg) {
  const container = document.getElementById('toast-container');
  const el = document.createElement('div');
  el.className = 'toast';
  el.textContent = msg;
  container.appendChild(el);
  setTimeout(() => el.remove(), 3800);
}

function getStatementBadge(st) {
  if (st.status === 'paga') {
    return `<span class="badge badge-paid">✔ Paga • Cartão Liberado</span>`;
  }
  if (st.status === 'acordo') {
    return `<span class="badge badge-agreement">🤝 Fatura Parcelada</span>`;
  }
  if (st.promise_date) {
    return `<span class="badge badge-due-today">📅 Promessa: ${formatDateBR(st.promise_date)}</span>`;
  }
  if (st.bucket === 'preventive') {
    return `<span class="badge badge-preventive">📄 ${st.status_label}</span>`;
  }
  if (st.bucket === 'due_today') {
    return `<span class="badge badge-due-today">⏰ ${st.status_label}</span>`;
  }
  if (st.bucket === 'overdue_light') {
    return `<span class="badge badge-overdue-light">⚠️ ${st.status_label}</span>`;
  }
  if (st.bucket === 'overdue_blocked') {
    return `<span class="badge badge-overdue-critical">🔒 ${st.status_label}</span>`;
  }
  return `<span class="badge badge-overdue-critical">🚨 ${st.status_label}</span>`;
}

function getLeadStageBadge(stage) {
  const map = {
    novo_lead: '<span class="badge badge-preventive">🆕 Proposta Digital</span>',
    mesa_credito: '<span class="badge badge-due-today">🔎 Mesa / Biometria</span>',
    aprovado_sem_compra: '<span class="badge badge-agreement">🎫 Voucher Emitido (Falta 1ª Compra)</span>',
    cartao_ativo: '<span class="badge badge-paid">💳 Cartão Ativo no PDV</span>',
    bloqueado_atraso: '<span class="badge badge-overdue-critical">🔒 Bloqueado no Caixa (D+5)</span>',
    recusado: '<span class="badge badge-overdue-critical">✕ Recusado Política</span>'
  };
  return map[stage] || stage;
}

function getScoreBadge(score) {
  const cls = score >= 740 ? 'tier-A' : score >= 560 ? 'tier-B' : score >= 450 ? 'tier-C' : 'tier-D';
  return `<span class="score-pill ${cls}">${score} pts</span>`;
}

async function loadState() {
  try {
    const res = await fetch('/api/state');
    APP_STATE = await res.json();
    renderAll();
  } catch (err) {
    console.error('Erro ao carregar estado:', err);
  }
}

function renderAll() {
  if (!APP_STATE) return;
  const k = APP_STATE.kpis;
  const store = APP_STATE.store || {};

  if (store.brand_color) {
    document.documentElement.style.setProperty('--primary', store.brand_color);
  }
  document.getElementById('sidebar-card-name').textContent = store.card_brand_name || 'Cartão Armarinhos Fernando';
  document.getElementById('sidebar-store-name').textContent = store.store_name || 'Armarinhos Fernando';
  document.getElementById('sidebar-block-days').textContent = `D+${store.auto_block_days || 5} de atraso`;
  document.getElementById('sidebar-rates-summary').textContent =
    `Anuidade: ${formatBRL(store.anuidade_faturada_brl || 14.9)} • Seguro: ${formatBRL(store.seguro_protegido_brl || 9.9)} • Rotativo: ${store.rotativo_interest_pct || 11.9}%`;

  const posRateEl = document.getElementById('pos-crediario-rate');
  if (posRateEl) posRateEl.textContent = `${store.crediario_interest_pct || 4.99}% a.m.`;

  document.getElementById('nav-overdue-count').textContent = k.overdue_count;
  document.getElementById('nav-leads-count').textContent = APP_STATE.leads.length;
  document.getElementById('nav-pos-count').textContent = (APP_STATE.pos_transactions || []).length;
  document.getElementById('nav-statements-count').textContent = APP_STATE.statements.length;
  document.getElementById('nav-rules-count').textContent = APP_STATE.rules.length;
  const teamCountEl = document.getElementById('nav-team-count');
  if (teamCountEl) teamCountEl.textContent = (APP_STATE.admin_users || []).length;

  renderDashboard();
  renderLeadsFunnelAndTable();
  renderPosAndPromoters();
  renderStatementsTable();
  renderRulesGrid();
  populateSimulatorSelect();
  renderAgreementsTable();
  populateSettingsForm();
  renderStaffTable();
  recalcRoiSimulator();
}

function switchTab(tabName) {
  if (CURRENT_ADMIN_USER) {
    const allowed = getAllowedTabsForRole(CURRENT_ADMIN_USER.role);
    if (!allowed.includes(tabName)) {
      showToast('🔒 Acesso Restrito: Seu perfil não possui permissão para acessar este módulo.');
      return;
    }
  }
  CURRENT_TAB = tabName;
  document.querySelectorAll('.tab-section').forEach(sec => {
    sec.style.display = 'none';
  });
  const activeSec = document.getElementById(`tab-${tabName}`);
  if (activeSec) activeSec.style.display = 'block';

  document.querySelectorAll('.nav-btn').forEach(btn => {
    btn.classList.toggle('active', btn.dataset.tab === tabName);
  });

  const titles = {
    dashboard: ['Visão Executiva', ''],
    leads: ['Mesa de Crédito & Limites', ''],
    pos: ['Vendas & Caixa WebPOS', ''],
    statements: ['Faturas & Cobrança', ''],
    rules: ['Régua Automática de Cobrança', ''],
    simulator: ['Acordos & Parcelamento', ''],
    roi: ['Viabilidade Financeira & ROI — Armarinhos Fernando', ''],
    environments: ['Links dos Portais', ''],
    team: ['Equipe & Acessos por Nicho', ''],
    settings: ['Configurações da Loja', '']
  };

  if (titles[tabName]) {
    document.getElementById('page-title').textContent = titles[tabName][0];
    document.getElementById('page-subtitle').textContent = titles[tabName][1];
  }
}

function reloadDualEnvironments() {
  const f1 = document.getElementById('iframe-client-app');
  const f2 = document.getElementById('iframe-store-webpos');
  if (f1 && f1.contentWindow) f1.contentWindow.location.reload();
  if (f2 && f2.contentWindow) f2.contentWindow.location.reload();
  loadState();
  showToast('🔄 Telas do App do Cliente e do WebPOS sincronizadas com sucesso!');
}

function renderDashboard() {
  const k = APP_STATE.kpis;
  const kpiContainer = document.getElementById('dashboard-kpis');
  kpiContainer.innerHTML = `
    <div class="kpi-card">
      <div class="kpi-label">Portadores & Vouchers 1ª Compra</div>
      <div class="kpi-value">${k.total_leads} Cartões (${k.approval_rate_pct}%)</div>
      <div class="kpi-sub">
        <span><strong>${k.pending_leads}</strong> na Mesa</span> •
        <span style="color:var(--primary); font-weight:700;">${k.inactive_vouchers} Vouchers prontos p/ 1ª compra</span>
      </div>
    </div>
    <div class="kpi-card warning">
      <div class="kpi-label">Limite Concedido vs. Usado no PDV</div>
      <div class="kpi-value">${formatBRL(k.total_limit_used)}</div>
      <div class="kpi-sub">
        <span>De <strong>${formatBRL(k.total_limit_granted)}</strong> concedidos (${k.active_cards} cartões ativos)</span>
      </div>
    </div>
    <div class="kpi-card success">
      <div class="kpi-label">Receita Anuidade + Seguros + PIX</div>
      <div class="kpi-value" style="color:var(--emerald);">${formatBRL(k.total_recovered)}</div>
      <div class="kpi-sub">
        <span>+<strong>${formatBRL(k.monthly_ancillary_revenue)}/mês</strong> em Anuidade & Seguro (${k.seguros_ativos} ativos)</span>
      </div>
    </div>
    <div class="kpi-card danger">
      <div class="kpi-label">Faturas Vencidas & Bloqueios PDV</div>
      <div class="kpi-value" style="color:var(--rose);">${formatBRL(k.total_overdue_updated)}</div>
      <div class="kpi-sub">
        <span><strong>${k.blocked_cards} cartões bloqueados</strong></span> •
        <span>+${formatBRL(k.total_charges_accrued)} em rotativo</span>
      </div>
    </div>
  `;

  // Priority Queue
  const pqTbody = document.getElementById('priority-queue-tbody');
  const queue = APP_STATE.priority_queue.slice(0, 6);
  pqTbody.innerHTML = queue.map(st => `
    <tr>
      <td>
        <div style="font-weight:700; color:var(--text-main);">${st.client_name}</div>
        <div style="font-size:11.5px; color:var(--text-muted);">
          💳 <code>6060 •••• ${st.card_number_last4}</code> • Venc: ${formatDateBR(st.due_date)}
        </div>
      </td>
      <td>${getStatementBadge(st)}</td>
      <td><span class="rule-stage-pill">${st.recommended_stage}</span></td>
      <td>
        <div style="font-weight:800; color:var(--text-main);">${formatBRL(st.updated_amount)}</div>
        ${st.total_charges > 0
          ? `<div style="font-size:11px; color:var(--rose);">+${formatBRL(st.total_charges)} rotativo/multa</div>`
          : `<div style="font-size:11px; color:var(--emerald);">Mínimo: ${formatBRL(st.minimum_payment)}</div>`
        }
      </td>
      <td>
        <div style="display:flex; gap:6px; flex-wrap:wrap;">
          <button class="btn btn-sm btn-primary" onclick="openComposerForStatement(${st.id})">💬 Cobrar</button>
          <a href="/portal?id=${st.id}" class="btn btn-sm btn-outline" title="Abrir Super App do Cliente">📱 Super App</a>
        </div>
      </td>
    </tr>
  `).join('');

  // Aging Bars
  const aging = APP_STATE.aging;
  const maxAging = Math.max(
    1,
    aging.preventive.amount,
    aging.due_today.amount,
    aging.overdue_light.amount,
    aging.overdue_blocked.amount,
    aging.overdue_critical.amount
  );

  const agingItems = [
    { key: 'preventive', color: '#2563eb' },
    { key: 'due_today', color: '#d97706' },
    { key: 'overdue_light', color: '#d4af37' },
    { key: 'overdue_blocked', color: '#e11d48' },
    { key: 'overdue_critical', color: '#881337' }
  ];

  const agingContainer = document.getElementById('aging-bars-container');
  agingContainer.innerHTML = agingItems.map(item => {
    const bucket = aging[item.key];
    const pct = Math.round((bucket.amount / maxAging) * 100);
    return `
      <div class="aging-row">
        <div class="aging-meta">
          <span>${bucket.label} (${bucket.count} fatura${bucket.count === 1 ? '' : 's'})</span>
          <span>${formatBRL(bucket.amount)}</span>
        </div>
        <div class="aging-bar-track">
          <div class="aging-bar-fill" style="width:${Math.max(pct, bucket.amount > 0 ? 6 : 0)}%; background:${item.color};"></div>
        </div>
      </div>
    `;
  }).join('');

  document.getElementById('ancillary-revenue-total').textContent = `${formatBRL(k.monthly_ancillary_revenue)} / mês`;

  // Logs Table
  const logsTbody = document.getElementById('logs-tbody');
  logsTbody.innerHTML = APP_STATE.logs.slice(0, 9).map(log => `
    <tr>
      <td style="white-space:nowrap; font-size:12px; color:var(--text-muted);">${log.created_at}</td>
      <td>
        <div style="font-weight:700;">${log.client_name || log.recipient}</div>
        <div style="font-size:11.5px; color:var(--text-muted);">
          ${log.card_number_last4 ? `💳 Final ${log.card_number_last4}` : ''} ${log.statement_code ? `• ${log.statement_code}` : ''}
        </div>
      </td>
      <td><span class="rule-stage-pill" style="font-size:11px;">${log.stage_code}</span></td>
      <td style="font-size:12.5px;">${log.channel}</td>
      <td style="max-width:360px; font-size:12px; color:var(--text-secondary);">
        ${(log.message_body || '').slice(0, 115)}${(log.message_body || '').length > 115 ? '...' : ''}
      </td>
      <td>
        <span class="badge ${log.outcome.includes('Pago') || log.outcome.includes('Aprovada') || log.outcome.includes('APROVADO') ? 'badge-paid' : 'badge-agreement'}">
          ${log.outcome}
        </span>
      </td>
    </tr>
  `).join('');
}

// LEADS / BIOMETRIA / VOUCHERS FUNNEL & TABLE
function renderLeadsFunnelAndTable() {
  if (!APP_STATE) return;
  const leads = APP_STATE.leads;

  const cols = [
    {
      title: '1. Mesa de Crédito & Biometria',
      items: leads.filter(l => l.lead_stage === 'novo_lead' || l.lead_stage === 'mesa_credito'),
      renderAction: l => `
        <button class="btn btn-sm btn-emerald" style="width:100%;" onclick="changeLeadStage(${l.id}, 'aprovado_sem_compra')">
          ✔ Aprovar & Emitir Voucher (${formatBRL(l.approved_limit)})
        </button>
      `
    },
    {
      title: '2. Voucher 1ª Compra Liberado',
      items: leads.filter(l => l.lead_stage === 'aprovado_sem_compra'),
      renderAction: l => `
        <div style="display:flex; gap:5px;">
          <button class="btn btn-sm btn-primary" style="flex:1;" onclick="openComposerForLead(${l.id}, 'ATIVACAO')">💬 Enviar Voucher</button>
          <button class="btn btn-sm btn-emerald" style="flex:1;" onclick="openPosPurchaseModal(${l.id})">🛒 Passar 1ª Compra</button>
        </div>
      `
    },
    {
      title: '3. Cartão Ativo (Comprando)',
      items: leads.filter(l => l.lead_stage === 'cartao_ativo'),
      renderAction: l => `
        <div style="display:flex; gap:5px;">
          <button class="btn btn-sm btn-outline" style="flex:1;" onclick="openComposerForLead(${l.id}, 'MELHOR-DIA')">🛒 Melhor Dia</button>
          <button class="btn btn-sm btn-emerald" style="flex:1;" onclick="openPosPurchaseModal(${l.id})">🛒 Venda PDV</button>
        </div>
      `
    },
    {
      title: '4. Bloqueado no PDV (D+5)',
      items: leads.filter(l => l.lead_stage === 'bloqueado_atraso'),
      renderAction: l => `
        <button class="btn btn-sm btn-primary" style="width:100%; background:var(--rose);" onclick="openComposerForLead(${l.id}, 'D+5')">
          🔓 Cobrar PIX p/ Liberar no Caixa
        </button>
      `
    }
  ];

  const funnelGrid = document.getElementById('leads-funnel-grid');
  funnelGrid.innerHTML = cols.map(col => `
    <div class="funnel-col">
      <div class="funnel-col-header">
        <span>${col.title}</span>
        <span class="badge badge-agreement">${col.items.length}</span>
      </div>
      ${col.items.map(l => `
        <div class="lead-mini-card">
          <div style="display:flex; justify-content:space-between; align-items:flex-start;">
            <div style="font-weight:700; font-size:13px;">${l.full_name}</div>
            ${getScoreBadge(l.credit_score)}
          </div>
          <div style="font-size:11px; color:var(--emerald); font-weight:700;">
            📸 ${l.biometria_status}
          </div>
          <div style="font-size:11.5px; color:var(--text-muted);">
            🎫 Voucher: <code>${l.voucher_code}</code> • PIN: <code>${l.card_pin}</code>
          </div>
          <div style="font-size:11.5px; color:var(--text-secondary);">
            📍 ${l.store_branch} • 👤 ${l.promoter_name}
          </div>
          <div style="font-size:12px; font-weight:700; color:var(--primary);">
            Limite: ${formatBRL(l.approved_limit)} (Disp: ${formatBRL(l.available_limit)})
          </div>
          <div style="margin-top:4px;">${col.renderAction(l)}</div>
        </div>
      `).join('') || '<div style="font-size:12px; color:var(--text-muted); text-align:center; padding:12px;">Nenhum cliente nesta etapa</div>'}
    </div>
  `).join('');

  renderLeadsTable();
}

function renderLeadsTable() {
  if (!APP_STATE) return;
  const q = (document.getElementById('lead-search')?.value || '').toLowerCase().trim();
  const filtered = APP_STATE.leads.filter(l => {
    if (!q) return true;
    const hay = `${l.full_name} ${l.cpf} ${l.store_branch} ${l.promoter_name} ${l.card_number_full} ${l.voucher_code}`.toLowerCase();
    return hay.includes(q);
  });

  const tbody = document.getElementById('leads-tbody');
  tbody.innerHTML = filtered.map(l => {
    const pctUsed = l.approved_limit > 0 ? Math.min(100, Math.round((l.used_limit / l.approved_limit) * 100)) : 0;
    return `
      <tr>
        <td>
          <div style="font-weight:700;">${l.full_name}</div>
          <div style="font-size:11.5px; color:var(--text-muted);">CPF: ${l.cpf} • RG: ${l.rg_cnh || '—'}</div>
          ${l.mother_name ? `<div style="font-size:11px; color:var(--text-secondary);">👩 Mãe: ${l.mother_name} • 💼 ${l.occupation || 'Autônomo'}</div>` : ''}
          ${l.address_summary ? `<div style="font-size:10.5px; color:var(--text-muted);">📍 ${l.address_summary}</div>` : ''}
          <div style="font-size:11px; color:var(--emerald); font-weight:600; margin-top:2px;">📸 ${l.biometria_status}</div>
        </td>
        <td>
          <div style="font-weight:600;">${l.store_branch}</div>
          <div style="font-size:11.5px; color:var(--primary);">${l.promoter_name}</div>
        </td>
        <td>
          ${getLeadStageBadge(l.lead_stage)}
          <div style="font-size:11.5px; font-family:monospace; margin-top:3px;">💳 ${l.card_number_full}</div>
          <div style="font-size:11px; color:var(--text-muted);">🎫 Voucher 1ª Compra: <strong>${l.voucher_code}</strong> (PIN: ${l.card_pin})</div>
        </td>
        <td>
          <div style="font-weight:700;">Vence dia ${l.due_day}</div>
          <div style="font-size:11px; color:var(--emerald); font-weight:700;">🛒 Melhor Dia: dia ${l.best_purchase_day}</div>
        </td>
        <td>
          <div style="font-size:11.5px; cursor:pointer;" onclick="toggleHolderService(${l.id}, 'has_seguro_protegido', ${l.has_seguro_protegido ? 'false' : 'true'})" title="Clique para Ativar/Desativar Seguro Conta Protegida">
            ${l.has_seguro_protegido ? '<span class="badge badge-paid">🛡️ Seguro Conta Protegida (Ativo)</span>' : '<span class="badge" style="background:#e2e8f0; color:#475569;">+ Ativar Seguro</span>'}
          </div>
          <div style="font-size:11px; color:var(--text-muted); margin-top:4px; cursor:pointer;" onclick="toggleHolderService(${l.id}, 'has_sms_alerta', ${l.has_sms_alerta ? 'false' : 'true'})" title="Clique para Ativar/Desativar SMS Alerta">
            ${l.has_sms_alerta ? '📲 SMS Alerta Ativo (Desativar)' : '📲 + Ativar SMS Alerta'}
          </div>
        </td>
        <td style="min-width:170px;">
          <div style="display:flex; justify-content:space-between; font-size:11.5px; font-weight:700; margin-bottom:4px;">
            <span>Disp: ${formatBRL(l.available_limit)}</span>
            <span style="color:var(--text-muted);">Total: ${formatBRL(l.approved_limit)}</span>
          </div>
          <div class="aging-bar-track" style="height:7px;">
            <div class="aging-bar-fill" style="width:${pctUsed}%; background:${pctUsed > 80 ? 'var(--rose)' : 'var(--primary)'};"></div>
          </div>
        </td>
        <td>
          <div style="display:flex; gap:5px; flex-wrap:wrap;">
            ${l.lead_stage === 'novo_lead' || l.lead_stage === 'mesa_credito' ? `
              <button class="btn btn-sm btn-emerald" onclick="changeLeadStage(${l.id}, 'aprovado_sem_compra')">✔ Emitir Voucher</button>
            ` : ''}
            <button class="btn btn-sm btn-outline" onclick="openEditHolderModal(${l.id})" title="Editar Limite, Senha PIN, Vencimento e Dados">✏️ Editar / Limite</button>
            <button class="btn btn-sm btn-primary" onclick="openComposerForLead(${l.id}, '${l.first_purchase_done ? 'MELHOR-DIA' : 'ATIVACAO'}')">💬 WhatsApp</button>
            <button class="btn btn-sm btn-emerald" onclick="openPosPurchaseModal(${l.id})">🛒 PDV</button>
          </div>
        </td>
      </tr>
    `;
  }).join('');
}

async function toggleHolderService(leadId, fieldName, newVal) {
  const payload = { lead_id: leadId };
  payload[fieldName] = newVal;
  await fetch('/api/leads/update-holder', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload)
  });
  showToast(`✅ Serviço do portador atualizado com sucesso!`);
  await loadState();
}

function openEditHolderModal(leadId) {
  if (!APP_STATE) return;
  const l = APP_STATE.leads.find(x => x.id === Number(leadId));
  if (!l) return;
  document.getElementById('edit-holder-id').value = l.id;
  document.getElementById('edit-holder-name').value = l.full_name;
  document.getElementById('edit-holder-cpf').value = l.cpf;
  document.getElementById('edit-holder-wa').value = l.whatsapp;
  document.getElementById('edit-holder-limit').value = l.approved_limit;
  document.getElementById('edit-holder-dueday').value = String(l.due_day || 10);
  document.getElementById('edit-holder-pin').value = l.card_pin || '1234';
  document.getElementById('edit-holder-score').value = l.credit_score || 680;
  document.getElementById('edit-holder-stage').value = l.lead_stage;
  document.getElementById('edit-holder-branch').value = l.store_branch;
  document.getElementById('edit-holder-promoter').value = l.promoter_name;
  document.getElementById('edit-holder-seguro').checked = Boolean(l.has_seguro_protegido);
  document.getElementById('edit-holder-sms').checked = Boolean(l.has_sms_alerta);
  document.getElementById('modal-edit-holder').classList.add('open');
}

async function saveHolderEdits() {
  const payload = {
    lead_id: Number(document.getElementById('edit-holder-id').value),
    full_name: document.getElementById('edit-holder-name').value,
    cpf: document.getElementById('edit-holder-cpf').value,
    whatsapp: document.getElementById('edit-holder-wa').value,
    approved_limit: parseFloat(document.getElementById('edit-holder-limit').value || 1000),
    due_day: parseInt(document.getElementById('edit-holder-dueday').value || 10, 10),
    card_pin: document.getElementById('edit-holder-pin').value || '1234',
    credit_score: parseInt(document.getElementById('edit-holder-score').value || 680, 10),
    lead_stage: document.getElementById('edit-holder-stage').value,
    store_branch: document.getElementById('edit-holder-branch').value,
    promoter_name: document.getElementById('edit-holder-promoter').value,
    has_seguro_protegido: document.getElementById('edit-holder-seguro').checked,
    has_sms_alerta: document.getElementById('edit-holder-sms').checked
  };

  const res = await fetch('/api/leads/update-holder', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload)
  });
  const data = await res.json();
  if (data.ok) {
    closeModal('modal-edit-holder');
    showToast(`💾 Dados e Limite (${formatBRL(data.approved_limit)}) atualizados! Melhor dia: ${data.best_purchase_day}.`);
    await loadState();
  }
}

async function changeLeadStage(leadId, newStage) {
  await fetch('/api/leads/stage', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ lead_id: leadId, lead_stage: newStage })
  });
  showToast('🪪 Cartão & Voucher de 1ª Compra liberados para o caixa!');
  await loadState();
}

// POS & PROMOTERS TAB
function renderPosAndPromoters() {
  if (!APP_STATE) return;
  const txs = APP_STATE.pos_transactions || [];
  const approvedSales = txs.filter(t => t.status === 'APROVADA');
  const invoiceReceipts = txs.filter(t => t.status === 'RECEBIDA CAIXA');
  const reversedTxs = txs.filter(t => t.status === 'ESTORNADA');

  const sumSales = approvedSales.reduce((acc, t) => acc + Number(t.total_with_interest || 0), 0);
  const sumInvoices = invoiceReceipts.reduce((acc, t) => acc + Number(t.total_with_interest || 0), 0);
  const sumReversed = reversedTxs.reduce((acc, t) => acc + Number(t.total_with_interest || 0), 0);

  const kpiGrid = document.getElementById('webpos-kpis-grid');
  if (kpiGrid) {
    kpiGrid.innerHTML = `
      <div class="kpi-card">
        <div class="kpi-label">Vendas Aprovadas WebPOS (NSU)</div>
        <div class="kpi-value" style="color:var(--emerald);">${formatBRL(sumSales)}</div>
        <div class="kpi-sub"><span><strong>${approvedSales.length} cupons</strong> autorizados no caixa</span></div>
      </div>
      <div class="kpi-card success">
        <div class="kpi-label">Faturas Recebidas na Gaveta</div>
        <div class="kpi-value">${formatBRL(sumInvoices)}</div>
        <div class="kpi-sub"><span><strong>${invoiceReceipts.length} baixas</strong> c/ liberação imediata de limite</span></div>
      </div>
      <div class="kpi-card danger">
        <div class="kpi-label">Estornos / Cancelamentos NSU</div>
        <div class="kpi-value" style="color:var(--rose);">${formatBRL(sumReversed)}</div>
        <div class="kpi-sub"><span><strong>${reversedTxs.length} transações</strong> estornadas pelo supervisor</span></div>
      </div>
      <div class="kpi-card warning">
        <div class="kpi-label">Liquidação Prevista Lojista (D+2)</div>
        <div class="kpi-value">${formatBRL(sumSales * 0.975)}</div>
        <div class="kpi-sub"><span>Repasse líquido Loja + <strong>${formatBRL(sumInvoices)}</strong> em caixa</span></div>
      </div>
    `;
  }

  const invSel = document.getElementById('quick-pos-invoice-select');
  if (invSel) {
    const openSts = (APP_STATE.statements || []).filter(s => s.status !== 'paga');
    invSel.innerHTML = openSts.map(s => `
      <option value="${s.id}">${s.statement_code} — ${s.client_name} (Final ${s.card_number_last4}) • ${formatBRL(s.updated_amount)}</option>
    `).join('');
  }

  const boostSel = document.getElementById('quick-pos-boost-holder');
  if (boostSel) {
    boostSel.innerHTML = (APP_STATE.leads || []).map(l => `
      <option value="${l.id}">${l.full_name} (Disp: ${formatBRL(l.available_limit)})</option>
    `).join('');
  }

  const pTbody = document.getElementById('promoters-tbody');
  if (pTbody) {
    pTbody.innerHTML = (APP_STATE.promoters_ranking || []).map((p, idx) => `
      <tr>
        <td>
          <div style="font-weight:700;">${idx === 0 ? '🥇 ' : idx === 1 ? '🥈 ' : '🥉 '}${p.promoter_name}</div>
        </td>
        <td style="font-size:12px; color:var(--text-secondary);">${p.store_branch}</td>
        <td style="font-weight:700;">${p.cards_captured} propostas</td>
        <td>
          <span class="badge badge-paid">${p.activated_first_purchase} ativados c/ compra</span>
        </td>
        <td>
          <span class="badge badge-agreement">🛡️ ${p.seguros_sold} seguros</span>
        </td>
        <td style="font-weight:800; color:var(--emerald); font-size:14px;">
          ${formatBRL(p.commission_brl)}
        </td>
      </tr>
    `).join('');
  }

  const txTbody = document.getElementById('pos-transactions-tbody');
  if (txTbody) {
    const modLabels = {
      rotativo_vista: '🛒 Rotativo Vista (40d)',
      parcelado_sem_juros: '🛍️ Parcelado Loja s/ Juros',
      crediario_com_juros: '💳 Crediário c/ Juros',
      saque_facil: '💵 Saque Fácil no Caixa',
      recebimento_fatura: '💸 Recebimento Fatura Caixa'
    };
    txTbody.innerHTML = txs.map(tx => `
      <tr>
        <td>
          <div style="font-weight:800; font-family:monospace; color:var(--primary);">${tx.nsu_code}</div>
          <div style="font-size:11px; color:var(--text-muted);">${tx.created_at}</div>
        </td>
        <td>
          <div style="font-weight:700;">${tx.client_name || 'Portador'}</div>
          <div style="font-size:11px; color:var(--text-muted);">💳 Final ${tx.card_number_last4 || ''}</div>
        </td>
        <td>
          <div style="font-weight:600; font-size:12px;">${tx.store_branch}</div>
          <div style="font-size:11px; color:var(--text-muted);">${tx.cashier_name}</div>
        </td>
        <td><span class="badge badge-preventive">${modLabels[tx.modality] || tx.modality}</span></td>
        <td style="font-size:12px; color:var(--text-secondary);">${tx.items_description}</td>
        <td>${formatBRL(tx.gross_amount)}</td>
        <td style="font-weight:800;">
          ${formatBRL(tx.total_with_interest)}
          <div style="font-size:11px; color:var(--text-muted);">${tx.installments}x de ${formatBRL(tx.installment_amount)}</div>
        </td>
        <td>
          <span class="badge ${tx.status === 'ESTORNADA' ? 'badge-overdue-critical' : 'badge-paid'}">
            ${tx.status === 'ESTORNADA' ? '↩️ ESTORNADA' : '✔ ' + tx.status}
          </span>
        </td>
        <td>
          ${tx.status === 'APROVADA' ? `
            <button class="btn btn-sm btn-outline" style="color:var(--rose); border-color:#fecdd3;" onclick="reversePosTransaction(${tx.id})">
              ↩️ Estornar NSU
            </button>
          ` : '<span style="font-size:11px; color:var(--text-muted);">—</span>'}
        </td>
      </tr>
    `).join('');
  }
}

async function submitQuickPosInvoicePayment() {
  const statement_id = Number(document.getElementById('quick-pos-invoice-select')?.value);
  const payment_method = document.getElementById('quick-pos-invoice-method')?.value || 'Dinheiro no Caixa (Espécie)';
  const payment_type = document.getElementById('quick-pos-invoice-type')?.value || 'total';
  if (!statement_id) return;

  const res = await fetch('/api/pos-pay-invoice', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ statement_id, payment_method, payment_type, cashier_name: 'Caixa 01 - WebPOS' })
  });
  const data = await res.json();
  if (data.ok) {
    showToast(`💸 Fatura recebida no caixa (${data.rec_nsu})! Limite liberado e cartão desbloqueado!`);
    await loadState();
  } else {
    showToast(`⛔ ${data.error || 'Erro no recebimento'}`);
  }
}

async function submitQuickPosLimitBoost() {
  const lead_id = Number(document.getElementById('quick-pos-boost-holder')?.value);
  if (!lead_id) return;
  const res = await fetch('/api/pos-limit-boost', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ lead_id, boost_amount: 600, operator_name: 'Balcão WebPOS' })
  });
  const data = await res.json();
  if (data.ok) {
    showToast(`🚀 Limite aumentado para ${formatBRL(data.new_limit)} no WebPOS!`);
    await loadState();
  }
}

async function reversePosTransaction(txId) {
  const res = await fetch('/api/pos-reverse', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ tx_id: txId, reason: 'Estorno solicitado no painel WebPOS', supervisor_name: 'Supervisor Fiscal' })
  });
  const data = await res.json();
  if (data.ok) {
    showToast(`↩️ NSU ${data.nsu_code} estornado com sucesso! Limite devolvido ao cartão.`);
    await loadState();
  } else {
    showToast(`⛔ ${data.error || 'Erro ao estornar NSU'}`);
  }
}

// STATEMENTS TABLE
function setStatementFilter(filter) {
  STATEMENT_FILTER = filter;
  const pills = document.querySelectorAll('#statement-filter-pills .filter-pill');
  const mapIdx = { all: 0, overdue: 1, blocked: 2, open: 3, paid: 4 };
  pills.forEach((p, idx) => p.classList.toggle('active', idx === mapIdx[filter]));
  renderStatementsTable();
}

function renderStatementsTable() {
  if (!APP_STATE) return;
  const q = (document.getElementById('statement-search')?.value || '').toLowerCase().trim();

  const filtered = APP_STATE.statements.filter(st => {
    if (STATEMENT_FILTER === 'overdue' && !(st.status === 'vencida')) return false;
    if (STATEMENT_FILTER === 'blocked' && !st.card_blocked_by_delay) return false;
    if (STATEMENT_FILTER === 'open' && !(st.status !== 'paga' && st.days_overdue <= 0)) return false;
    if (STATEMENT_FILTER === 'paid' && !(st.status === 'paga' || st.status === 'acordo')) return false;

    if (q) {
      const hay = `${st.statement_code} ${st.client_name} ${st.cpf} ${st.items_summary} ${st.card_number_last4}`.toLowerCase();
      if (!hay.includes(q)) return false;
    }
    return true;
  });

  const tbody = document.getElementById('statements-tbody');
  tbody.innerHTML = filtered.map(st => `
    <tr>
      <td>
        <div style="font-weight:700;">${st.statement_code}</div>
        <div style="font-size:11px; color:var(--text-muted);">Corte: ${formatDateBR(st.closing_date)}</div>
      </td>
      <td>
        <div style="font-weight:700;">${st.client_name}</div>
        <div style="font-size:11.5px; color:var(--text-muted);">CPF: ${st.cpf} • 💳 Final <strong>${st.card_number_last4}</strong></div>
        ${st.promise_note ? `<div style="font-size:11px; color:var(--amber); margin-top:2px;">📌 ${st.promise_note}</div>` : ''}
      </td>
      <td style="max-width:260px; font-size:12px; color:var(--text-secondary);">
        ${st.items_summary}
      </td>
      <td style="white-space:nowrap; font-weight:700;">${formatDateBR(st.due_date)}</td>
      <td>${getStatementBadge(st)}</td>
      <td style="white-space:nowrap;">
        <div style="font-weight:700;">${formatBRL(st.original_amount)}</div>
        <div style="font-size:10.5px; color:var(--text-muted);">Mínimo (15%): ${formatBRL(st.minimum_payment)}</div>
      </td>
      <td style="white-space:nowrap; color:${st.total_charges > 0 ? 'var(--rose)' : 'var(--text-muted)'}; font-weight:700;">
        ${st.total_charges > 0 ? '+' + formatBRL(st.total_charges) : 'R$ 0,00'}
      </td>
      <td style="white-space:nowrap; font-weight:800; font-size:14px;">${formatBRL(st.updated_amount)}</td>
      <td>
        ${st.status === 'paga' ? `
          <span style="font-size:12px; color:var(--emerald); font-weight:700;">✔ Paga em ${formatDateBR(st.paid_date)}</span>
        ` : `
          <div style="display:flex; gap:5px; flex-wrap:wrap;">
            <button class="btn btn-sm btn-primary" onclick="openComposerForStatement(${st.id})">💬 Cobrar (${st.recommended_stage})</button>
            <a href="/portal?id=${st.id}" class="btn btn-sm btn-outline">📱 App</a>
            <button class="btn btn-sm btn-outline" onclick="openPromiseModal(${st.id})">📅 Promessa</button>
            <button class="btn btn-sm btn-emerald" onclick="markStatementPaid(${st.id}, ${st.updated_amount})" title="Dar baixa PIX e desbloquear cartão no PDV">✔ Baixar PIX</button>
          </div>
        `}
      </td>
    </tr>
  `).join('');
}

// NEW LEAD MODAL (PRIME)
function openNewLeadModal() {
  previewLeadCreditCalc();
  document.getElementById('modal-new-lead').classList.add('open');
}

function previewLeadCreditCalc() {
  const income = Number(document.getElementById('lead-income')?.value || 3800);
  const score = Number(document.getElementById('lead-score')?.value || 690);
  const dueDay = Number(document.getElementById('lead-dueday')?.value || 10);
  const minScore = APP_STATE?.store?.min_score_auto_approve || 550;

  let bestDay = dueDay - 9;
  if (bestDay <= 0) bestDay += 30;

  let limit = 0;
  let tier = 'Private Label Loja';
  if (score >= 740) {
    limit = Math.round((income * 0.60) / 10) * 10;
    tier = 'VIP Internacional';
  } else if (score >= 560) {
    limit = Math.round((income * 0.38) / 10) * 10;
    tier = 'Gold Mais';
  } else if (score >= 440) {
    limit = Math.round((income * 0.22) / 10) * 10;
    tier = 'Private Label Loja';
  }

  const approved = score >= minScore;
  const box = document.getElementById('lead-credit-preview');
  if (box) {
    box.innerHTML = `
      <div style="display:flex; justify-content:space-between; align-items:center;">
        <div>
          <strong>Análise Instantânea Motor Prime + Biometria Facial:</strong><br/>
          Decisão: <strong>${approved ? '✅ APROVADO C/ VOUCHER DE 1ª COMPRA IMEDIATA' : score < 440 ? '❌ RECUSADO PELA POLÍTICA' : '🔎 ENVIAR P/ MESA DE CRÉDITO'}</strong><br/>
          Categoria: <strong>${tier}</strong> • Melhor Dia de Compra: <strong>Todo dia ${bestDay}</strong>
        </div>
        <div style="text-align:right;">
          <div style="font-size:11px;">LIMITE APROVADO NA HORA</div>
          <div style="font-size:21px; font-weight:800; color:var(--emerald);">${formatBRL(limit)}</div>
        </div>
      </div>
    `;
  }
}

async function submitNewLead() {
  const payload = {
    full_name: document.getElementById('lead-name').value || 'Cliente Novo Balcão',
    cpf: document.getElementById('lead-cpf').value,
    rg_cnh: document.getElementById('lead-rg').value,
    mother_name: document.getElementById('lead-mother').value,
    whatsapp: document.getElementById('lead-wa').value,
    occupation: document.getElementById('lead-job').value,
    declared_income: Number(document.getElementById('lead-income').value || 3800),
    credit_score: Number(document.getElementById('lead-score').value || 690),
    due_day: Number(document.getElementById('lead-dueday').value || 10),
    card_pin: document.getElementById('lead-pin').value || '1234',
    store_branch: document.getElementById('lead-branch').value,
    promoter_name: document.getElementById('lead-seller').value,
    has_seguro_protegido: document.getElementById('lead-seguro').checked,
    has_sms_alerta: document.getElementById('lead-sms').checked
  };

  const res = await fetch('/api/leads', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload)
  });
  const data = await res.json();
  closeModal('modal-new-lead');
  showToast(`🎉 Cartão aprovado! Voucher ${data.voucher_code} emitido com limite de ${formatBRL(data.approved_limit)}!`);
  await loadState();
  switchTab('leads');
}

// POS PURCHASE MODAL
function openPosPurchaseModal(preselectedLeadId) {
  if (!APP_STATE) return;
  const sel = document.getElementById('pos-lead-select');
  const eligible = APP_STATE.leads.filter(l => l.lead_stage !== 'recusado');
  sel.innerHTML = eligible.map(l =>
    `<option value="${l.id}">${l.full_name} — Cartão Final ${l.card_number_last4} | Voucher: ${l.voucher_code} (Disp: ${formatBRL(l.available_limit)})${l.first_purchase_done === 0 ? ' 🎁 [10% OFF 1ª Compra]' : ''}${l.lead_stage === 'bloqueado_atraso' ? ' 🔒 [BLOQUEADO]' : ''}</option>`
  ).join('');

  if (preselectedLeadId) {
    sel.value = String(preselectedLeadId);
  }
  onPosModalLeadChange();
  document.getElementById('modal-pos-purchase').classList.add('open');
}

function onPosModalLeadChange() {
  if (!APP_STATE) return;
  const leadId = Number(document.getElementById('pos-lead-select')?.value);
  const holder = APP_STATE.leads.find(l => l.id === leadId);
  if (holder) {
    const pinInput = document.getElementById('pos-pin');
    if (pinInput) pinInput.value = holder.card_pin || '1234';
  }
  updatePosModalPreview();
}

function updatePosModalPreview() {
  if (!APP_STATE) return;
  const leadId = Number(document.getElementById('pos-lead-select')?.value);
  const holder = APP_STATE.leads.find(l => l.id === leadId);
  if (!holder) return;

  const mod = document.getElementById('pos-modality')?.value || 'parcelado_sem_juros';
  const amount = Number(document.getElementById('pos-amount')?.value || 0);
  const installments = Number(document.getElementById('pos-installments')?.value || 1);
  const store = APP_STATE.store || {};

  const isFirst = holder.first_purchase_done === 0;
  const discPct = isFirst ? Number(store.first_purchase_discount_pct || 10) : 0;
  const netAmount = +(amount * (1 - discPct / 100)).toFixed(2);

  let totalWithInterest = netAmount;
  let ratePct = 0;
  if ((mod === 'crediario_com_juros' || mod === 'saque_facil') && installments >= 1) {
    ratePct = Number(store.crediario_interest_pct || 4.99);
    totalWithInterest = +(netAmount * Math.pow(1 + ratePct / 100, installments)).toFixed(2);
  }
  const instVal = +(totalWithInterest / Math.max(1, installments)).toFixed(2);

  const box = document.getElementById('pos-modal-calc-preview');
  if (box) {
    box.innerHTML = `
      <div style="display:flex; justify-content:space-between; align-items:center;">
        <div>
          <strong>Simulação no Caixa (${holder.full_name}):</strong><br/>
          • Limite Disponível: <strong>${formatBRL(holder.available_limit)}</strong> | PIN do Cartão: <code>${holder.card_pin}</code><br/>
          • Valor Líquido${isFirst ? ` (-${discPct}% 1ª Compra)` : ''}: <strong>${formatBRL(netAmount)}</strong> ${ratePct > 0 ? `(+${ratePct}% a.m. Crediário)` : '(Sem Juros)'}
        </div>
        <div style="text-align:right;">
          <div style="font-size:11px; color:var(--text-muted);">PLANO NO CUPOM</div>
          <div style="font-size:18px; font-weight:800; color:var(--emerald);">${installments}x de ${formatBRL(instVal)}</div>
          <div style="font-size:11px;">Total: ${formatBRL(totalWithInterest)}</div>
        </div>
      </div>
    `;
  }
}

async function submitPosPurchase() {
  const lead_id = Number(document.getElementById('pos-lead-select').value);
  const modality = document.getElementById('pos-modality').value;
  const cashier_name = document.getElementById('pos-cashier').value;
  const items_summary = document.getElementById('pos-items').value;
  const amount = Number(document.getElementById('pos-amount').value || 350);
  const installments = Number(document.getElementById('pos-installments').value || 1);
  const due_date = document.getElementById('pos-duedate').value;
  const pin_code = document.getElementById('pos-pin')?.value || '';
  const force_supervisor = Boolean(document.getElementById('pos-force-supervisor')?.checked);

  const res = await fetch('/api/pos-purchase', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ lead_id, modality, cashier_name, items_summary, amount, installments, due_date, pin_code, force_supervisor })
  });
  const data = await res.json();
  if (!res.ok || data.error) {
    showToast(`❌ ${data.error || 'Erro ao autorizar venda no PDV'}`);
    return;
  }
  closeModal('modal-pos-purchase');
  showToast(`✅ Venda Aprovada (${data.nsu_code})! Fatura gerada: ${formatBRL(data.statement_total)} (c/ Anuidade/Seguro).`);
  await loadState();
}

// WHATSAPP COMPOSER
async function openComposerForStatement(statementId) {
  const st = APP_STATE.statements.find(s => s.id === statementId);
  document.getElementById('comp-statement-id').value = statementId;
  document.getElementById('comp-lead-id').value = st ? st.holder_id : '';
  if (st) {
    document.getElementById('comp-stage').value = st.recommended_stage;
  }
  await refreshComposerPreview();
  document.getElementById('modal-composer').classList.add('open');
}

async function openComposerForLead(leadId, defaultStage) {
  document.getElementById('comp-statement-id').value = '';
  document.getElementById('comp-lead-id').value = leadId;
  document.getElementById('comp-stage').value = defaultStage || 'ATIVACAO';
  await refreshComposerPreview();
  document.getElementById('modal-composer').classList.add('open');
}

async function refreshComposerPreview() {
  const statementId = document.getElementById('comp-statement-id').value;
  const leadId = document.getElementById('comp-lead-id').value;
  const stageCode = document.getElementById('comp-stage').value;

  const res = await fetch('/api/preview-message', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      statement_id: statementId ? Number(statementId) : null,
      lead_id: leadId ? Number(leadId) : null,
      stage_code: stageCode
    })
  });
  const data = await res.json();

  document.getElementById('composer-subtitle').textContent =
    `${data.lead.full_name} • Cartão ${data.lead.card_number_full} • Voucher: ${data.lead.voucher_code}`;
  document.getElementById('comp-subject').value = data.subject;
  document.getElementById('comp-body').value = data.body;
  document.getElementById('comp-wa-link').href = `${data.whatsapp_url}${encodeURIComponent(data.body)}`;
}

function copyComposerText() {
  navigator.clipboard.writeText(document.getElementById('comp-body').value);
  showToast('📋 Mensagem copiada para a área de transferência!');
}

async function confirmSendCollection() {
  const statementId = document.getElementById('comp-statement-id').value;
  const leadId = Number(document.getElementById('comp-lead-id').value);
  const stageCode = document.getElementById('comp-stage').value;
  const channel = document.getElementById('comp-channel').value;
  const messageBody = document.getElementById('comp-body').value;

  await fetch('/api/send-collection', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      statement_id: statementId ? Number(statementId) : null,
      lead_id: leadId,
      stage_code: stageCode,
      channel,
      message_body: messageBody,
      outcome: `Disparo ${stageCode} enviado via ${channel}`
    })
  });

  closeModal('modal-composer');
  showToast(`✅ Disparo (${stageCode}) registrado no histórico do portador!`);
  await loadState();
}

async function dispatchPriorityBatch() {
  const res = await fetch('/api/dispatch-batch', { method: 'POST' });
  const data = await res.json();
  showToast(`🚀 Régua Prime disparada em lote! ${data.dispatched_count} titulares acionados no WhatsApp.`);
  await loadState();
}

async function markStatementPaid(statementId, amount) {
  await fetch('/api/mark-paid', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ statement_id: statementId, paid_amount: amount })
  });
  showToast(`💸 Fatura liquidada! Limite recomposto e cartão DESBLOQUEADO no PDV da loja!`);
  await loadState();
}

function openPromiseModal(statementId) {
  document.getElementById('prom-statement-id').value = statementId;
  document.getElementById('modal-promise').classList.add('open');
}

async function savePromise() {
  const statementId = Number(document.getElementById('prom-statement-id').value);
  const promiseDate = document.getElementById('prom-date').value;
  const promiseNote = document.getElementById('prom-note').value;

  await fetch('/api/register-promise', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ statement_id: statementId, promise_date: promiseDate, promise_note: promiseNote })
  });
  closeModal('modal-promise');
  showToast('📅 Promessa de pagamento registrada!');
  await loadState();
}

// RULES GRID
function renderRulesGrid() {
  if (!APP_STATE) return;
  const grid = document.getElementById('rules-grid');
  grid.innerHTML = APP_STATE.rules.map(rule => `
    <div class="rule-card ${rule.active ? '' : 'inactive'}">
      <div style="display:flex; justify-content:space-between; align-items:center;">
        <span class="rule-stage-pill">${rule.stage_code}</span>
        <span class="badge ${rule.stage_code === 'ATIVACAO' || rule.stage_code === 'MELHOR-DIA' ? 'badge-paid' : rule.tone === 'amigavel' ? 'badge-preventive' : 'badge-overdue-critical'}">
          ${rule.channel}
        </span>
      </div>
      <div style="font-weight:700; font-size:14px;">${rule.title}</div>
      <div class="rule-preview-box">${rule.message_template}</div>
      <div style="display:flex; justify-content:space-between; margin-top:auto; padding-top:8px;">
        <button class="btn btn-sm btn-outline" onclick="toggleRuleActive(${rule.id})">
          ${rule.active ? '⏸ Pausar' : '▶ Ativar'}
        </button>
        <button class="btn btn-sm btn-primary" onclick="openRuleModal(${rule.id})">✏️ Editar</button>
      </div>
    </div>
  `).join('');
}

function openRuleModal(ruleId) {
  if (ruleId) {
    const r = APP_STATE.rules.find(x => x.id === ruleId);
    if (!r) return;
    document.getElementById('rule-id').value = r.id;
    document.getElementById('rule-code').value = r.stage_code;
    document.getElementById('rule-offset').value = r.day_offset;
    document.getElementById('rule-channel').value = r.channel;
    document.getElementById('rule-title').value = r.title;
    document.getElementById('rule-tone').value = r.tone;
    document.getElementById('rule-subject').value = r.subject_template;
    document.getElementById('rule-message').value = r.message_template;
  } else {
    document.getElementById('rule-id').value = '';
    document.getElementById('rule-code').value = 'D+10';
    document.getElementById('rule-offset').value = 10;
    document.getElementById('rule-channel').value = 'WhatsApp Oficial';
    document.getElementById('rule-title').value = 'Campanha Desbloqueio Imediato';
    document.getElementById('rule-tone').value = 'firme';
    document.getElementById('rule-subject').value = 'Libere seu {{nome_cartao}} hoje!';
    document.getElementById('rule-message').value = 'Olá {{cliente}}, pague sua fatura {{fatura}} de {{valor_atualizado}} via PIX e libere seu cartão no caixa da loja: {{link_portal}}';
  }
  document.getElementById('modal-rule').classList.add('open');
}

async function saveRule() {
  const id = document.getElementById('rule-id').value;
  await fetch('/api/rules', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      id: id ? Number(id) : null,
      stage_code: document.getElementById('rule-code').value,
      day_offset: Number(document.getElementById('rule-offset').value || 0),
      channel: document.getElementById('rule-channel').value,
      title: document.getElementById('rule-title').value,
      tone: document.getElementById('rule-tone').value,
      active: true,
      subject_template: document.getElementById('rule-subject').value,
      message_template: document.getElementById('rule-message').value
    })
  });
  closeModal('modal-rule');
  showToast('⚡ Regra da régua Prime salva!');
  await loadState();
}

async function toggleRuleActive(ruleId) {
  const r = APP_STATE.rules.find(x => x.id === ruleId);
  if (!r) return;
  await fetch('/api/rules', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      id: r.id,
      title: r.title,
      channel: r.channel,
      tone: r.tone,
      active: !r.active,
      subject_template: r.subject_template,
      message_template: r.message_template
    })
  });
  await loadState();
}

// SIMULATOR & VIRTUAL STORE CARD PREVIEW
function populateSimulatorSelect() {
  if (!APP_STATE) return;
  const sel = document.getElementById('sim-statement-select');
  const curr = sel.value;
  const openSt = APP_STATE.statements.filter(s => s.status !== 'paga');
  sel.innerHTML = openSt.map(s =>
    `<option value="${s.id}">${s.statement_code} — ${s.client_name} (Final ${s.card_number_last4} | Atualizado: ${formatBRL(s.updated_amount)})</option>`
  ).join('');
  if (curr && openSt.some(s => String(s.id) === String(curr))) {
    sel.value = curr;
  }
  updateSimulatorView();
}

function getSimData() {
  if (!APP_STATE) return null;
  const stId = Number(document.getElementById('sim-statement-select')?.value);
  const st = APP_STATE.statements.find(s => s.id === stId) || APP_STATE.statements[0];
  if (!st) return null;

  const discountPct = Number(document.getElementById('sim-discount-range')?.value || 85);
  const installments = Number(document.getElementById('sim-installments')?.value || 1);
  const downPct = Number(document.getElementById('sim-downpayment-pct')?.value || 33);
  const firstDue = document.getElementById('sim-first-due')?.value || '2026-10-16';

  const savings = st.total_charges * (discountPct / 100.0);
  const finalAmount = st.original_amount + (st.total_charges - savings);
  const downPayment = installments <= 1 ? finalAmount : finalAmount * (downPct / 100.0);
  const installmentValue = installments <= 1 ? finalAmount : (finalAmount - downPayment) / (installments - 1);

  return { st, discountPct, installments, downPct, firstDue, savings, finalAmount, downPayment, installmentValue };
}

function updateSimulatorView() {
  const sim = getSimData();
  if (!sim) return;

  document.getElementById('sim-discount-label').textContent = `${sim.discountPct}% OFF nos juros do rotativo`;
  document.getElementById('sim-open-portal-btn').href = `/portal?id=${sim.st.id}`;

  document.getElementById('sim-breakdown-box').innerHTML = `
    <div style="display:grid; grid-template-columns: repeat(3, 1fr); gap:10px; margin-bottom:12px;">
      <div>
        <div style="font-size:11px; color:var(--text-muted);">FATURA (COMPRAS + ENCARGOS)</div>
        <div style="font-size:15px; font-weight:700;">${formatBRL(sim.st.original_amount)}</div>
      </div>
      <div>
        <div style="font-size:11px; color:var(--text-muted);">JUROS ROTATIVO + MULTA</div>
        <div style="font-size:15px; font-weight:700; color:var(--rose);">+${formatBRL(sim.st.total_charges)}</div>
      </div>
      <div>
        <div style="font-size:11px; color:var(--text-muted);">DESCONTO CONCEDIDO</div>
        <div style="font-size:15px; font-weight:700; color:var(--emerald);">-${formatBRL(sim.savings)}</div>
      </div>
    </div>
    <div style="padding-top:12px; border-top:1px dashed #cbd5e1; display:flex; justify-content:space-between; align-items:center;">
      <div>
        <div style="font-size:11px; font-weight:700; color:var(--text-secondary);">VALOR FINAL DO ACORDO</div>
        <div style="font-size:22px; font-weight:800; color:var(--primary);">${formatBRL(sim.finalAmount)}</div>
      </div>
      <div style="text-align:right;">
        <div style="font-size:12.5px; font-weight:700;">
          ${sim.installments === 1
            ? `À Vista no PIX: ${formatBRL(sim.finalAmount)}`
            : `Entrada PIX ${formatBRL(sim.downPayment)} + ${sim.installments - 1}x de ${formatBRL(sim.installmentValue)}`
          }
        </div>
        <div style="font-size:11px; color:var(--emerald); font-weight:600;">⚡ Desbloqueia o cartão no PDV após pagamento da entrada</div>
      </div>
    </div>
  `;

  const store = APP_STATE.store || {};
  const availLimit = Math.max(0, (sim.st.approved_limit || 1500) - (sim.st.used_limit || 500));

  document.getElementById('virtual-card-preview-box').innerHTML = `
    <div class="store-card-visual ${sim.st.card_blocked_by_delay ? 'blocked' : sim.st.card_tier.includes('VIP') ? 'vip' : ''}">
      <div style="display:flex; justify-content:space-between; align-items:center;">
        <div>
          <div style="font-size:17px; font-weight:800; letter-spacing:0.3px;">${store.card_brand_name || 'Cartão Armarinhos Fernando'}</div>
          <div style="font-size:11px; opacity:0.85;">${store.store_name || 'Rede Varejo'} • BIN Private Label 6060</div>
        </div>
        <span class="badge ${sim.st.card_blocked_by_delay ? 'badge-overdue-critical' : 'badge-paid'}">
          ${sim.st.card_blocked_by_delay ? '🔒 Bloqueado no PDV' : `✨ ${sim.st.card_tier}`}
        </span>
      </div>
      <div class="card-chip"></div>
      <div style="font-family:monospace; font-size:18px; letter-spacing:2.5px; margin-bottom:12px;">
        ${sim.st.card_number_full || `6060 8421 •••• ${sim.st.card_number_last4}`}
      </div>
      <div style="display:flex; justify-content:space-between; align-items:flex-end; font-size:12px;">
        <div>
          <div style="font-size:10px; opacity:0.75;">PORTADOR TITULAR</div>
          <div style="font-weight:700; text-transform:uppercase;">${sim.st.client_name}</div>
        </div>
        <div style="text-align:right;">
          <div style="font-size:10px; opacity:0.75;">LIMITE DISPONÍVEL</div>
          <div style="font-weight:800; font-size:14px;">${formatBRL(availLimit)} / ${formatBRL(sim.st.approved_limit)}</div>
        </div>
      </div>
    </div>

    <div style="margin-top:16px; background:var(--bg-subtle); border:1px solid var(--border-color); border-radius:10px; padding:14px;">
      <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:8px;">
        <span style="font-size:12px; font-weight:700;">Fatura Aberta no Super App do Cliente:</span>
        <a href="/portal?id=${sim.st.id}" class="btn btn-sm btn-primary">Abrir Super App c/ QR Code PIX →</a>
      </div>
      <div style="font-size:12px; color:var(--text-secondary);">
        • <strong>Composição:</strong> ${sim.st.items_summary}<br/>
        • <strong>Linha Digitável Boleto:</strong> <code>${sim.st.digitable_line || '23793.38128 60084.219018...'}</code>
      </div>
    </div>
  `;
}

async function formalizeAgreement() {
  const sim = getSimData();
  if (!sim) return;

  await fetch('/api/agreements', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      statement_id: sim.st.id,
      discount_pct: sim.discountPct,
      installments: sim.installments,
      down_payment_pct: sim.downPct,
      first_due_date: sim.firstDue
    })
  });
  showToast(`🤝 Parcelamento formalizado e cartão de ${sim.st.client_name} reabilitado no caixa!`);
  await loadState();
}

function renderAgreementsTable() {
  if (!APP_STATE) return;
  const tbody = document.getElementById('agreements-tbody');
  if (!APP_STATE.agreements.length) {
    tbody.innerHTML = `<tr><td colspan="8" style="text-align:center; color:var(--text-muted);">Nenhum parcelamento de fatura formalizado ainda.</td></tr>`;
    return;
  }
  tbody.innerHTML = APP_STATE.agreements.map(a => `
    <tr>
      <td style="font-weight:800; color:var(--primary);">${a.agreement_code}</td>
      <td>
        <div style="font-weight:700;">${a.client_name}</div>
        <div style="font-size:11px; color:var(--text-muted);">CPF: ${a.signer_cpf || a.cpf} • Final ${a.card_number_last4 || ''}</div>
      </td>
      <td>${a.statement_code}</td>
      <td>${formatBRL(a.updated_amount)}</td>
      <td style="color:var(--emerald); font-weight:700;">${a.discount_pct}% OFF nos juros</td>
      <td style="font-weight:800;">${formatBRL(a.final_amount)}</td>
      <td>
        ${a.installments === 1
          ? `À Vista no PIX`
          : `Entrada ${formatBRL(a.down_payment)} + ${a.installments - 1}x ${formatBRL(a.installment_value)}`
        }
      </td>
      <td>
        <span class="badge badge-agreement">${a.status}</span>
        ${a.signature_hash ? `<div style="font-size:10px; font-family:monospace; color:var(--text-muted); margin-top:2px;">Hash: ${a.signature_hash}</div>` : ''}
      </td>
    </tr>
  `).join('');
}

// STORE & TARIFFS SETTINGS
function populateSettingsForm() {
  if (!APP_STATE || !APP_STATE.store) return;
  const s = APP_STATE.store;
  document.getElementById('set-store-name').value = s.store_name || '';
  document.getElementById('set-card-name').value = s.card_brand_name || '';
  document.getElementById('set-brand-color').value = s.brand_color || '#d4af37';
  document.getElementById('set-cnpj').value = s.cnpj || '';
  document.getElementById('set-pix-key').value = s.pix_key || '';
  document.getElementById('set-anuidade').value = s.anuidade_faturada_brl ?? 14.90;
  document.getElementById('set-seguro').value = s.seguro_protegido_brl ?? 9.90;
  document.getElementById('set-sms').value = s.sms_alerta_brl ?? 5.90;
  document.getElementById('set-rotativo-pct').value = s.rotativo_interest_pct ?? 11.9;
  document.getElementById('set-installment-pct').value = s.crediario_interest_pct ?? 4.99;
  document.getElementById('set-fine-pct').value = s.fine_pct ?? 2.0;
  document.getElementById('set-min-score').value = s.min_score_auto_approve ?? 550;
  document.getElementById('set-block-days').value = s.auto_block_days ?? 5;
  document.getElementById('set-discount-first').value = s.first_purchase_discount_pct ?? 10.0;
  const supWa = document.getElementById('set-support-wa');
  if (supWa) supWa.value = s.support_whatsapp || '5511980005544';
  const comCard = document.getElementById('set-comissao-card');
  if (comCard) comCard.value = s.comissao_promotor_brl ?? 6.00;
  const comSeg = document.getElementById('set-comissao-seguro');
  if (comSeg) comSeg.value = s.comissao_seguro_brl ?? 3.50;
}

async function saveStoreSettings() {
  const payload = {
    store_name: document.getElementById('set-store-name').value,
    card_brand_name: document.getElementById('set-card-name').value,
    brand_color: document.getElementById('set-brand-color').value,
    cnpj: document.getElementById('set-cnpj').value,
    pix_key: document.getElementById('set-pix-key').value,
    support_whatsapp: document.getElementById('set-support-wa')?.value || '5511980005544',
    anuidade_faturada_brl: parseFloat(document.getElementById('set-anuidade').value || '14.90'),
    seguro_protegido_brl: parseFloat(document.getElementById('set-seguro').value || '9.90'),
    sms_alerta_brl: parseFloat(document.getElementById('set-sms').value || '5.90'),
    comissao_promotor_brl: parseFloat(document.getElementById('set-comissao-card')?.value || '6.00'),
    comissao_seguro_brl: parseFloat(document.getElementById('set-comissao-seguro')?.value || '3.50'),
    rotativo_interest_pct: parseFloat(document.getElementById('set-rotativo-pct').value || '11.9'),
    crediario_interest_pct: parseFloat(document.getElementById('set-installment-pct').value || '4.99'),
    fine_pct: parseFloat(document.getElementById('set-fine-pct').value || '2.0'),
    min_score_auto_approve: parseInt(document.getElementById('set-min-score').value || '550', 10),
    auto_block_days: parseInt(document.getElementById('set-block-days').value || '5', 10),
    first_purchase_discount_pct: parseFloat(document.getElementById('set-discount-first').value || '10.0')
  };

  await fetch('/api/store', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload)
  });
  showToast('🏪 Parâmetros da Operação Prime atualizados em toda a rede!');
  await loadState();
}

function closeModal(id) {
  document.getElementById(id).classList.remove('open');
}

function copyExternalUrl(url, label) {
  navigator.clipboard.writeText(url);
  showToast(`🔗 Link externo copiado: ${label}`);
}

let LAST_DB_VER = null;
let LAST_CODE_VER = null;

async function pollLiveSync() {
  try {
    const res = await fetch('/api/sync-version');
    if (!res.ok) return;
    const data = await res.json();
    if (!data.ok) return;

    if (data.external_links) {
      const cadCode = document.getElementById('ext-code-cadastro');
      const cadBtn = document.getElementById('ext-btn-cadastro');
      if (cadCode) cadCode.textContent = 'https://promotorarmarinhosfernando.com';
      if (cadBtn && data.external_links.cadastro_url) cadBtn.href = data.external_links.cadastro_url;

      const cCode = document.getElementById('ext-code-cliente');
      const cBtn = document.getElementById('ext-btn-cliente');
      if (cCode) cCode.textContent = 'https://apparmarinhosfernando.com';
      if (cBtn && data.external_links.client_app_url) cBtn.href = data.external_links.client_app_url;

      const wCode = document.getElementById('ext-code-webpos');
      const wBtn = document.getElementById('ext-btn-webpos');
      if (wCode) wCode.textContent = 'https://webposarmarinhosfernando.com';
      if (wBtn && data.external_links.webpos_url) wBtn.href = data.external_links.webpos_url;

      const aCode = document.getElementById('ext-code-admin');
      const aBtn = document.getElementById('ext-btn-admin');
      if (aCode) aCode.textContent = 'https://admarmarinhosfernando.com';
      if (aBtn && data.external_links.admin_url) aBtn.href = data.external_links.admin_url;
    }

    if (LAST_CODE_VER && LAST_CODE_VER !== data.code_version) {
      window.location.reload();
      return;
    }
    LAST_CODE_VER = data.code_version;

    if (LAST_DB_VER && LAST_DB_VER !== data.db_version) {
      LAST_DB_VER = data.db_version;
      const activeEl = document.activeElement;
      const isTyping = activeEl && (activeEl.tagName === 'INPUT' || activeEl.tagName === 'TEXTAREA' || activeEl.tagName === 'SELECT');
      const hasOpenModal = document.querySelector('.modal-backdrop.open');
      if (!isTyping && !hasOpenModal) {
        await loadState();
        const f1 = document.getElementById('iframe-client-app');
        const f2 = document.getElementById('iframe-store-webpos');
        if (CURRENT_TAB === 'environments') {
          if (f1 && f1.contentWindow) f1.contentWindow.location.reload();
          if (f2 && f2.contentWindow) f2.contentWindow.location.reload();
        }
      }
    } else if (!LAST_DB_VER) {
      LAST_DB_VER = data.db_version;
    }
  } catch (e) {
    // ignore transient poll errors
  }
}

function recalcRoiSimulator() {
  const stores = Number(document.getElementById('roi-stores')?.value || 17);
  const daily = Number(document.getElementById('roi-daily')?.value || 30);
  const ticket = Number(document.getElementById('roi-ticket')?.value || 260);
  const attachPct = Number(document.getElementById('roi-attach')?.value || 65);

  const lblStores = document.getElementById('lbl-roi-stores');
  const lblDaily = document.getElementById('lbl-roi-daily');
  const lblTicket = document.getElementById('lbl-roi-ticket');
  const lblAttach = document.getElementById('lbl-roi-attach');

  if (lblStores) lblStores.textContent = `${stores} ${stores === 1 ? 'Loja' : 'Lojas'}`;
  if (lblDaily) lblDaily.textContent = `${daily} Cartões/dia`;
  if (lblTicket) lblTicket.textContent = formatBRL(ticket);
  if (lblAttach) lblAttach.textContent = `${attachPct}% da base`;

  const totalCards12m = stores * daily * 30 * 12;
  const activeSpendingCards = Math.round(totalCards12m * 0.60);
  const monthlyGmv = activeSpendingCards * ticket;

  const revAncillary = Math.round(activeSpendingCards * (attachPct / 100) * (14.90 + 9.90));
  const revInterest = Math.round(monthlyGmv * 0.22 * 0.089);
  const mdrSavings = Math.round(monthlyGmv * 0.022);
  const retailMarginIncremental = Math.round(monthlyGmv * 0.25 * 0.18);

  const totalMonthlyNet = revAncillary + revInterest + mdrSavings + retailMarginIncremental;
  const totalYearlyNet = totalMonthlyNet * 12;

  const kCards = document.getElementById('roi-kpi-cards');
  const kGmv = document.getElementById('roi-kpi-gmv');
  const kMo = document.getElementById('roi-kpi-monthly');
  const kYr = document.getElementById('roi-kpi-yearly');

  if (kCards) kCards.textContent = `${totalCards12m.toLocaleString('pt-BR')} Cartões`;
  if (kGmv) kGmv.textContent = formatBRL(monthlyGmv);
  if (kMo) kMo.textContent = formatBRL(totalMonthlyNet);
  if (kYr) kYr.textContent = formatBRL(totalYearlyNet);

  const tbody = document.getElementById('roi-pnl-tbody');
  if (tbody) {
    const rows = [
      ['1. Anuidade Faturada (R$ 14,90) + Seguro Conta Protegida (R$ 9,90)', `${attachPct}% de ${activeSpendingCards.toLocaleString('pt-BR')} faturas ativas`, revAncillary, revAncillary * 12],
      ['2. Receita de Crediário Loja & Parcelamento de Fatura', `22% da carteira em parcelamento c/ juros`, revInterest, revInterest * 12],
      ['3. Economia Direta de Taxa MDR de Maquininha (2,2%)', `Sobre ${formatBRL(monthlyGmv)} vendidos no cartão próprio`, mdrSavings, mdrSavings * 12],
      ['4. Margem Incremental de Aumento de Ticket Médio (+25% no Varejo/Atacado)', `Recompra fidelizada nas ${stores} lojas`, retailMarginIncremental, retailMarginIncremental * 12]
    ];
    tbody.innerHTML = rows.map(r => `
      <tr>
        <td style="font-weight:800; color:#fff;">${r[0]}</td>
        <td style="color:#94a3b8; font-size:12px;">${r[1]}</td>
        <td style="font-weight:800; color:#93c5fd;">${formatBRL(r[2])}</td>
        <td style="font-weight:900; color:#f3e5ab;">${formatBRL(r[3])}</td>
      </tr>
    `).join('') + `
      <tr style="background:rgba(212,175,55,0.12);">
        <td colspan="2" style="font-weight:900; color:#f3e5ab; font-size:14px;">🏆 RESULTADO LÍQUIDO TOTAL GERADO PELO CARTÃO ARMARINHOS FERNANDO</td>
        <td style="font-weight:900; color:#6ee7b7; font-size:15px;">${formatBRL(totalMonthlyNet)}/mês</td>
        <td style="font-weight:900; color:#f3e5ab; font-size:15px;">${formatBRL(totalYearlyNet)}/ano</td>
      </tr>
    `;
  }
}

function renderStaffTable() {
  const users = APP_STATE?.admin_users || [];
  const admCount = users.filter(u => u.role === 'adm_geral').length;
  const credCount = users.filter(u => u.role === 'credito').length;
  const cobCount = users.filter(u => u.role === 'cobranca').length;

  const elAdm = document.getElementById('kpi-team-adm');
  const elCred = document.getElementById('kpi-team-credito');
  const elCob = document.getElementById('kpi-team-cobranca');
  if (elAdm) elAdm.textContent = `${admCount} ${admCount === 1 ? 'operador' : 'operadores'}`;
  if (elCred) elCred.textContent = `${credCount} ${credCount === 1 ? 'analista' : 'analistas'}`;
  if (elCob) elCob.textContent = `${cobCount} ${cobCount === 1 ? 'operador' : 'operadores'}`;

  const tbody = document.getElementById('staff-table-body');
  if (!tbody) return;

  const permDesc = {
    adm_geral: '🛡️ Vê Tudo + Equipe & Configs',
    credito: '💳 Só Mesa de Crédito & Limites',
    cobranca: '📞 Só Faturas, Régua & Acordos'
  };

  tbody.innerHTML = users.map(u => `
    <tr>
      <td>
        <div style="font-weight:800; color:#fff;">${u.full_name}</div>
        <div style="font-size:11px; color:#94a3b8;">📍 ${u.branch || 'Matriz Centro'} • ${u.department || ''}</div>
      </td>
      <td style="font-family:monospace; font-weight:800; color:#f3e5ab;">${u.cpf}</td>
      <td>
        <span style="font-family:monospace; background:#090d16; padding:3px 8px; border-radius:6px; border:1px solid rgba(212,175,55,0.3); color:#93c5fd; font-weight:800;">${u.password}</span>
      </td>
      <td>
        <select class="select" style="padding:5px 8px; font-size:12px; font-weight:700;" onchange="updateStaffRole(${u.id}, this.value)">
          <option value="cobranca" ${u.role === 'cobranca' ? 'selected' : ''}>📞 Cobrança</option>
          <option value="credito" ${u.role === 'credito' ? 'selected' : ''}>💳 Crédito</option>
          <option value="adm_geral" ${u.role === 'adm_geral' ? 'selected' : ''}>🛡️ Adm Geral</option>
        </select>
      </td>
      <td style="font-size:11.5px; color:#cbd5e1; font-weight:700;">${permDesc[u.role] || u.role}</td>
      <td>
        ${u.status === 'ativo'
          ? '<span class="badge badge-paid">● Ativo</span>'
          : '<span class="badge badge-overdue-critical">🔒 Bloqueado</span>'}
      </td>
      <td>
        <div style="display:flex; gap:6px;">
          <button class="btn btn-sm btn-outline" onclick="promptUpdateStaffPassword(${u.id}, '${u.full_name.replace(/'/g, "\\'")}', '${u.password}')">🔑 Senha</button>
          <button class="btn btn-sm btn-outline" onclick="toggleStaffStatus(${u.id}, '${u.status}')">
            ${u.status === 'ativo' ? '🔒 Bloquear' : '🔓 Ativar'}
          </button>
          <button class="btn btn-sm btn-outline" style="color:#f87171; border-color:rgba(248,113,113,0.4);" onclick="deleteStaffMember(${u.id})">🗑️</button>
        </div>
      </td>
    </tr>
  `).join('');
}

async function createNewStaffMember() {
  const full_name = document.getElementById('new-staff-name')?.value.trim() || '';
  const cpf = document.getElementById('new-staff-cpf')?.value.trim() || '';
  const password = document.getElementById('new-staff-pass')?.value.trim() || '';
  const role = document.getElementById('new-staff-role')?.value || 'cobranca';
  const branch = document.getElementById('new-staff-branch')?.value || 'Matriz Centro';

  if (!full_name || !cpf || !password) {
    showToast('⚠️ Preencha Nome Completo, CPF e Senha do colaborador.');
    return;
  }

  const res = await fetch('/api/admin-users', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ full_name, cpf, password, role, branch })
  });
  const data = await res.json();
  if (!res.ok || !data.ok) {
    showToast(`❌ ${data.error || 'Erro ao cadastrar colaborador'}`);
    return;
  }
  document.getElementById('new-staff-name').value = '';
  document.getElementById('new-staff-cpf').value = '';
  showToast(`✅ Colaborador ${full_name} cadastrado no nicho ${role.toUpperCase()}!`);
  await loadState();
}

async function updateStaffRole(id, role) {
  await fetch('/api/admin-users/update', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ id, role })
  });
  showToast(`🔐 Permissão atualizada para o nicho: ${role.toUpperCase()}`);
  await loadState();
}

async function promptUpdateStaffPassword(id, name, currentPass) {
  const newPass = window.prompt(`Nova senha de acesso para ${name}:`, currentPass || '1234');
  if (!newPass || !newPass.trim()) return;
  await fetch('/api/admin-users/update', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ id, password: newPass.trim() })
  });
  showToast(`🔑 Senha de ${name} atualizada com sucesso!`);
  await loadState();
}

async function toggleStaffStatus(id, currentStatus) {
  const nextStatus = currentStatus === 'ativo' ? 'bloqueado' : 'ativo';
  await fetch('/api/admin-users/update', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ id, status: nextStatus })
  });
  showToast(nextStatus === 'ativo' ? '🔓 Acesso liberado!' : '🔒 Acesso bloqueado!');
  await loadState();
}

async function deleteStaffMember(id) {
  await fetch('/api/admin-users/delete', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ id })
  });
  showToast('🗑️ Cadastro removido da equipe.');
  await loadState();
}

async function submitAdminLogin() {
  const user = document.getElementById('adm-login-user')?.value.trim() || '';
  const pass = document.getElementById('adm-login-pass')?.value.trim() || '';
  const errBox = document.getElementById('adm-login-error');
  if (errBox) errBox.style.display = 'none';

  if (!user) {
    showToast('⚠️ Digite seu CPF para entrar no painel.');
    return;
  }
  if (!pass) {
    showToast('⚠️ Digite sua senha para entrar no painel.');
    return;
  }
  const res = await fetch('/api/auth/login', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ mode: 'admin', cpf: user, password: pass })
  });
  const data = await res.json();
  if (!res.ok || !data.ok) {
    if (errBox) {
      errBox.textContent = `❌ ${data.error || 'CPF ou senha inválidos'}`;
      errBox.style.display = 'block';
    }
    showToast(`❌ ${data.error || 'CPF ou senha inválidos'}`);
    return;
  }

  sessionStorage.setItem('bp_admin_user', JSON.stringify(data.admin_user));
  const overlay = document.getElementById('admin-login-overlay');
  const sb = document.getElementById('app-sidebar');
  const ma = document.getElementById('app-main-area');
  if (overlay) overlay.style.display = 'none';
  if (sb) sb.style.display = 'flex';
  if (ma) ma.style.display = 'flex';
  applyAdminRolePermissions(data.admin_user);
  showToast(`🔓 ${data.message}`);
}

function logoutAdminConsole() {
  CURRENT_ADMIN_USER = null;
  sessionStorage.removeItem('bp_admin_user');
  const overlay = document.getElementById('admin-login-overlay');
  const sb = document.getElementById('app-sidebar');
  const ma = document.getElementById('app-main-area');
  if (sb) sb.style.display = 'none';
  if (ma) ma.style.display = 'none';
  if (overlay) overlay.style.display = 'flex';
  showToast('🔒 Sessão encerrada com segurança.');
}

async function naturalKeepAliveAdmin10Min() {
  try {
    const r = await fetch('/api/sync-version?keepalive=1&cycle=10min', { cache: 'no-store' });
    if (r.ok) {
      const d = await r.json();
      if (d.external_links) {
        Object.values(d.external_links).forEach(u => {
          if (u && u.startsWith('https://')) {
            fetch(`${u}/api/sync-version?keepalive=1`, { mode: 'no-cors', cache: 'no-store' }).catch(() => {});
          }
        });
      }
    }
    await loadState();
  } catch (e) {}
}

window.addEventListener('DOMContentLoaded', () => {
  const savedAdmin = sessionStorage.getItem('bp_admin_user');
  if (savedAdmin) {
    try {
      const parsed = JSON.parse(savedAdmin);
      if (parsed && parsed.role) {
        const overlay = document.getElementById('admin-login-overlay');
        const sb = document.getElementById('app-sidebar');
        const ma = document.getElementById('app-main-area');
        if (overlay) overlay.style.display = 'none';
        if (sb) sb.style.display = 'flex';
        if (ma) ma.style.display = 'flex';
        applyAdminRolePermissions(parsed);
      }
    } catch (e) {}
  }
  loadState();
  pollLiveSync();
  setInterval(pollLiveSync, 2200);
  setInterval(naturalKeepAliveAdmin10Min, 45000);
  setInterval(naturalKeepAliveAdmin10Min, 600000);
});
