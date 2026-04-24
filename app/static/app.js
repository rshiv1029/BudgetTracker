/* ── Utilities ──────────────────────────────────────────────────────────── */

const api = {
  async get(path) {
    const r = await fetch(path);
    if (!r.ok) throw new Error(`GET ${path} → ${r.status}`);
    return r.json();
  },
  async post(path, body) {
    const r = await fetch(path, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
    if (!r.ok) {
      const t = await r.text();
      throw new Error(t);
    }
    return r.json();
  },
  async postForm(path, fd) {
    const r = await fetch(path, { method: "POST", body: fd });
    if (!r.ok) {
      const t = await r.text();
      throw new Error(t);
    }
    return r.json();
  },
  async patch(path, body) {
    const r = await fetch(path, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
    if (!r.ok) throw new Error(`PATCH ${path} → ${r.status}`);
    return r.json();
  },
  async put(path, body) {
    const r = await fetch(path, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
    if (!r.ok) throw new Error(`PUT ${path} → ${r.status}`);
    return r.json();
  },
  async del(path) {
    const r = await fetch(path, { method: "DELETE" });
    if (!r.ok) throw new Error(`DELETE ${path} → ${r.status}`);
  },
};

function fmt(amount) {
  const abs = Math.abs(amount).toLocaleString("en-US", {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  });
  return amount < 0 ? `-$${abs}` : `$${abs}`;
}

function fmtAbs(amount) {
  return (
    "$" +
    Math.abs(amount).toLocaleString("en-US", {
      minimumFractionDigits: 2,
      maximumFractionDigits: 2,
    })
  );
}

function fmtCompact(amount) {
  const abs = Math.abs(amount);
  const sign = amount < 0 ? "-" : "";
  if (abs >= 1000) return `${sign}$${(abs / 1000).toFixed(1)}k`;
  return `${sign}$${abs.toFixed(0)}`;
}

function currentMonthYear() {
  const d = new Date();
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}`;
}

function monthLabel(ym) {
  if (!ym) return "";
  const [y, m] = ym.split("-");
  return new Date(+y, +m - 1, 1).toLocaleDateString("en-US", {
    month: "long",
    year: "numeric",
  });
}

function prevMonth(ym) {
  const [y, m] = ym.split("-").map(Number);
  const d = new Date(y, m - 2, 1);
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}`;
}

function nextMonth(ym) {
  const [y, m] = ym.split("-").map(Number);
  const d = new Date(y, m, 1);
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}`;
}

function barWidth(pct) {
  return Math.min(pct * 100, 100) + "%";
}

function barClass(status) {
  return `bar-${status}`;
}
function badgeClass(status) {
  return `badge badge-${status}`;
}

// Chart.js global defaults
Chart.defaults.font.family = "'DM Sans', system-ui, sans-serif";
Chart.defaults.font.size = 12;
Chart.defaults.color = "#9999aa";
Chart.defaults.plugins.legend.labels.boxWidth = 10;
Chart.defaults.plugins.legend.labels.padding = 16;

/* ── Root App ───────────────────────────────────────────────────────────── */
function financeApp() {
  return {
    page: "dashboard",
    syncing: false,
    syncMsg: "",

    navigate(p) {
      this.page = p;
      window.dispatchEvent(new CustomEvent("page-changed", { detail: p }));
    },

    async syncAll() {
      this.syncing = true;
      this.syncMsg = "";
      try {
        const res = await api.post("/api/plaid/sync-all", {});
        const total = (res.results || []).reduce(
          (s, r) => s + (r.imported || 0),
          0,
        );
        this.syncMsg = `Synced! ${total} new transactions.`;
        setTimeout(() => {
          this.syncMsg = "";
        }, 4000);
      } catch (e) {
        this.syncMsg = "Sync failed: " + e.message;
      }
      this.syncing = false;
    },
  };
}

/* ── Dashboard ──────────────────────────────────────────────────────────── */
function dashboardApp() {
  return {
    insights: null,
    budgetStatus: [],
    loading: true,
    month_year: currentMonthYear(),
    charts: {},
    _loading: false,

    async init() {
      await this.load();
    },

    async load() {
      if (this._loading) return;
      this._loading = true;
      try {
        const [ins, budgets] = await Promise.all([
          api.get("/api/ai/insights?months=3"),
          api.get(`/api/budgets/status?month_year=${this.month_year}`),
        ]);
        this.insights = ins;
        this.budgetStatus = budgets;
        this.loading = false;
        await this.$nextTick();
        requestAnimationFrame(() => {
          requestAnimationFrame(() => {
            this.renderCharts();
          });
        });
      } catch (e) {
        console.error(e);
        this.loading = false;
      } finally {
        this._loading = false;
      }
    },

    get currentMonthData() {
      if (!this.insights) return null;
      const rows = this.insights.income_vs_expenses;
      return rows && rows.length ? rows[rows.length - 1] : null;
    },

    get totalIncome() {
      return this.currentMonthData?.income ?? 0;
    },
    get totalExpenses() {
      return this.currentMonthData?.expenses ?? 0;
    },
    get netThisMonth() {
      return this.totalIncome - this.totalExpenses;
    },

    renderCharts() {
      Object.values(this.charts).forEach((c) => c?.destroy());
      this.charts = {};
      if (!this.insights) return;
      this.renderCategoryPie();
      this.renderIncomeBar();
    },

    renderCategoryPie() {
      const el = document.getElementById("catPieChart");
      if (!el || el.offsetParent === null) return;
      const data = (this.insights.category_breakdown || []).slice(0, 8);
      if (!data.length) return;
      const colors = [
        "#3b7eff",
        "#f97316",
        "#8b5cf6",
        "#ec4899",
        "#10b981",
        "#f59e0b",
        "#06b6d4",
        "#94a3b8",
      ];
      this.charts.pie = new Chart(el, {
        type: "doughnut",
        data: {
          labels: data.map((r) => r.category),
          datasets: [
            {
              data: data.map((r) => r.total),
              backgroundColor: colors,
              borderWidth: 0,
              hoverOffset: 4,
            },
          ],
        },
        options: {
          responsive: true,
          maintainAspectRatio: false,
          plugins: {
            legend: {
              position: "right",
              labels: { usePointStyle: true, pointStyleWidth: 8 },
            },
            tooltip: {
              callbacks: {
                label: (ctx) => ` ${ctx.label}: $${ctx.parsed.toFixed(2)}`,
              },
            },
          },
          cutout: "65%",
        },
      });
    },

    renderIncomeBar() {
      const el = document.getElementById("incomeBarChart");
      if (!el || el.offsetParent === null) return;
      const data = this.insights.income_vs_expenses || [];
      if (!data.length) return;
      this.charts.bar = new Chart(el, {
        type: "bar",
        data: {
          labels: data.map((r) => r.month),
          datasets: [
            {
              label: "Income",
              data: data.map((r) => r.income),
              backgroundColor: "rgba(22,163,74,0.75)",
              borderRadius: 4,
              borderSkipped: false,
            },
            {
              label: "Expenses",
              data: data.map((r) => r.expenses),
              backgroundColor: "rgba(220,38,38,0.7)",
              borderRadius: 4,
              borderSkipped: false,
            },
          ],
        },
        options: {
          responsive: true,
          maintainAspectRatio: false,
          plugins: { legend: { position: "top" } },
          scales: {
            y: { beginAtZero: true, grid: { color: "rgba(0,0,0,0.04)" } },
            x: { grid: { display: false } },
          },
          borderRadius: 4,
        },
      });
    },

    fmt,
    fmtAbs,
    barWidth,
    barClass,
    badgeClass,
  };
}

/* ── Transactions ───────────────────────────────────────────────────────── */
function transactionsApp() {
  return {
    transactions: [],
    categories: [],
    loading: false,
    month_year: currentMonthYear(),
    filters: { category: "", search: "" },
    editingId: null,
    editCategory: "",

    async init() {
      this.categories = await api.get("/api/transactions/categories");
      await this.load();
    },

    async load() {
      this.loading = true;
      const p = new URLSearchParams();
      p.set("month_year", this.month_year);
      if (this.filters.category) p.set("category", this.filters.category);
      if (this.filters.search) p.set("search", this.filters.search);
      p.set("limit", "500");
      this.transactions = await api.get(`/api/transactions?${p}`);
      this.loading = false;
    },

    navMonth(dir) {
      this.month_year =
        dir === -1 ? prevMonth(this.month_year) : nextMonth(this.month_year);
      this.load();
    },

    get monthLabel() {
      return monthLabel(this.month_year);
    },

    startEdit(txn) {
      this.editingId = txn.id;
      this.editCategory = txn.category;
    },
    cancelEdit() {
      this.editingId = null;
    },

    async saveEdit(txn) {
      await api.patch(`/api/transactions/${txn.id}`, {
        category: this.editCategory,
      });
      txn.category = this.editCategory;
      this.editingId = null;
    },

    get totalExpenses() {
      return this.transactions
        .filter((t) => t.amount < 0 && !t.is_transfer)
        .reduce((s, t) => s + Math.abs(t.amount), 0);
    },
    get totalIncome() {
      return this.transactions
        .filter((t) => t.amount > 0 && !t.is_transfer)
        .reduce((s, t) => s + t.amount, 0);
    },

    fmt,
    fmtAbs,
  };
}

/* ── Accounts / Plaid ───────────────────────────────────────────────────── */
function accountsApp() {
  return {
    items: [],
    accounts: [],
    status: null,
    syncing: false,
    syncResults: null,
    error: null,

    async init() {
      await this.load();
    },

    async load() {
      const [items, status, nw] = await Promise.all([
        api.get("/api/plaid/items"),
        api.get("/api/plaid/status"),
        api.get("/api/net-worth/latest").catch(() => null),
      ]);
      this.items = items;
      this.status = status;
      this.accounts = nw?.accounts ?? [];
    },

    async connectBank() {
      this.error = null;
      if (!this.status?.configured) {
        this.error =
          "Plaid credentials not configured. See the setup instructions below.";
        return;
      }
      try {
        const { link_token } = await api.post("/api/plaid/link-token", {});
        this._openLink(link_token);
      } catch (e) {
        this.error = e.message;
      }
    },

    _openLink(token) {
      const handler = Plaid.create({
        token,
        onSuccess: async (publicToken, meta) => {
          this.syncing = true;
          try {
            const result = await api.post("/api/plaid/exchange-token", {
              public_token: publicToken,
              institution_name: meta.institution?.name ?? "Unknown Bank",
              institution_id: meta.institution?.institution_id ?? "",
            });
            this.syncResults = [result];
            await this.load();
          } catch (e) {
            this.error = e.message;
          }
          this.syncing = false;
        },
        onExit: (err) => {
          if (err)
            this.error =
              err.display_message ||
              err.error_message ||
              "Link exited with error";
        },
      });
      handler.open();
    },

    async syncAll() {
      this.syncing = true;
      this.syncResults = null;
      this.error = null;
      try {
        const res = await api.post("/api/plaid/sync-all", {});
        this.syncResults = res.results;
        await this.load();
      } catch (e) {
        this.error = e.message;
      }
      this.syncing = false;
    },

    async syncOne(itemId) {
      this.syncing = true;
      this.error = null;
      try {
        const res = await api.post(`/api/plaid/sync/${itemId}`, {});
        this.syncResults = [res];
        await this.load();
      } catch (e) {
        this.error = e.message;
      }
      this.syncing = false;
    },

    async disconnect(itemId, name) {
      if (
        !confirm(`Disconnect ${name}? Your existing transactions will be kept.`)
      )
        return;
      await api.del(`/api/plaid/items/${itemId}`);
      await this.load();
    },

    fmt,
  };
}

/* ── CSV Import ─────────────────────────────────────────────────────────── */
function importApp() {
  return {
    form: {
      account_name: "",
      account_type: "checking",
      institution: "",
      bank_profile: "sofi",
      run_ai: true,
    },
    file: null,
    result: null,
    error: null,
    loading: false,

    handleFile(e) {
      this.file = e.target.files[0];
    },

    async submit() {
      if (!this.file) {
        this.error = "Please select a CSV file.";
        return;
      }
      if (!this.form.account_name) {
        this.error = "Account name is required.";
        return;
      }
      this.error = null;
      this.result = null;
      this.loading = true;
      const fd = new FormData();
      fd.append("file", this.file);
      Object.entries(this.form).forEach(([k, v]) => fd.append(k, String(v)));
      try {
        this.result = await api.postForm("/api/transactions/import", fd);
      } catch (e) {
        this.error = e.message;
      }
      this.loading = false;
    },
    async detectTransfers() {
      try {
        const res = await api.post("/api/transactions/detect-transfers", {});
        this.result = { imported: 0, duplicates: 0, errors: 0, account_id: 0 };
        alert(res.message);
      } catch (e) {
        this.error = e.message;
      }
    },
  };
}

/* ── Budgets ────────────────────────────────────────────────────────────── */
function budgetsApp() {
  return {
    rules: [],
    status: [],
    categories: [],
    month_year: currentMonthYear(),
    form: {
      category: "",
      month_year: "",
      limit_amount: "",
      alert_threshold: 0.8,
    },
    showForm: false,
    editId: null,
    chart: null,

    async init() {
      this.categories = (await api.get("/api/transactions/categories")).map(
        (c) => c.name,
      );
      await this.load();
    },

    async load() {
      const [rules, status] = await Promise.all([
        api.get("/api/budgets"),
        api.get(`/api/budgets/status?month_year=${this.month_year}`),
      ]);
      this.rules = rules;
      this.status = status;
      this.$nextTick(() => this.renderChart());
    },

    navMonth(dir) {
      this.month_year =
        dir === -1 ? prevMonth(this.month_year) : nextMonth(this.month_year);
      this.load();
    },

    get monthLabel() {
      return monthLabel(this.month_year);
    },

    renderChart() {
      const el = document.getElementById("budgetRadarChart");
      if (!el || el.offsetParent === null || !this.status.length) return;
      if (this.chart) this.chart.destroy();
      const items = this.status.slice(0, 8);
      this.chart = new Chart(el, {
        type: "bar",
        data: {
          labels: items.map((b) =>
            b.category.length > 14 ? b.category.slice(0, 14) + "…" : b.category,
          ),
          datasets: [
            {
              label: "Spent",
              data: items.map((b) => b.actual_amount),
              backgroundColor: items.map((b) =>
                b.status === "over"
                  ? "rgba(220,38,38,0.75)"
                  : b.status === "warning"
                    ? "rgba(245,158,11,0.75)"
                    : "rgba(59,126,255,0.7)",
              ),
              borderRadius: 4,
              borderSkipped: false,
            },
            {
              label: "Budget",
              data: items.map((b) => b.limit_amount),
              backgroundColor: "rgba(0,0,0,0.06)",
              borderRadius: 4,
              borderSkipped: false,
            },
          ],
        },
        options: {
          indexAxis: "y",
          plugins: { legend: { position: "top" } },
          scales: {
            x: { beginAtZero: true, grid: { color: "rgba(0,0,0,0.04)" } },
            y: { grid: { display: false } },
          },
        },
      });
    },

    async save() {
      const body = {
        ...this.form,
        limit_amount: parseFloat(this.form.limit_amount),
      };
      if (!body.month_year) body.month_year = null;
      if (!body.category) return;
      try {
        if (this.editId) {
          await api.put(`/api/budgets/${this.editId}`, body);
        } else {
          await api.post("/api/budgets", body);
        }
        this.showForm = false;
        this.editId = null;
        this.form = {
          category: "",
          month_year: "",
          limit_amount: "",
          alert_threshold: 0.8,
        };
        await this.load();
      } catch (e) {
        alert("Error: " + e.message);
      }
    },

    async remove(id) {
      if (!confirm("Delete this budget rule?")) return;
      await api.del(`/api/budgets/${id}`);
      await this.load();
    },

    startEdit(rule) {
      this.editId = rule.id;
      this.form = {
        ...rule,
        month_year: rule.month_year || "",
        limit_amount: String(rule.limit_amount),
      };
      this.showForm = true;
    },

    fmtAbs,
    barWidth,
    barClass,
    badgeClass,
  };
}

/* ── Net Worth ──────────────────────────────────────────────────────────── */
function netWorthApp() {
  return {
    latest: null,
    history: [],
    accounts: [],
    snapForm: { account_id: "", balance: "", snapshot_date: "" },
    acctForm: { name: "", type: "checking", institution: "" },
    showSnapForm: false,
    showAcctForm: false,
    chart: null,
    loading: true,

    async init() {
      await this.load();
    },

    async load() {
      this.loading = true;
      const [latest, history, accounts] = await Promise.all([
        api.get("/api/net-worth/latest"),
        api.get("/api/net-worth/history"),
        api.get("/api/net-worth/accounts"),
      ]);
      this.latest = latest;
      this.history = history;
      this.accounts = accounts;
      this.loading = false;
      this.$nextTick(() => this.renderChart());
    },

    renderChart() {
      const el = document.getElementById("netWorthChart");
      if (!el || el.offsetParent === null || !this.history.length) return;
      if (this.chart) this.chart.destroy();
      this.chart = new Chart(el, {
        type: "line",
        data: {
          labels: this.history.map((r) => r.snapshot_date),
          datasets: [
            {
              label: "Net Worth",
              data: this.history.map((r) => r.total),
              borderColor: "#3b7eff",
              backgroundColor: (ctx) => {
                const g = ctx.chart.ctx.createLinearGradient(0, 0, 0, 200);
                g.addColorStop(0, "rgba(59,126,255,0.18)");
                g.addColorStop(1, "rgba(59,126,255,0)");
                return g;
              },
              fill: true,
              tension: 0.4,
              pointRadius: 3,
              pointHoverRadius: 6,
              borderWidth: 2,
            },
          ],
        },
        options: {
          responsive: true,
          maintainAspectRatio: false,
          plugins: {
            legend: { display: false },
            tooltip: {
              callbacks: {
                label: (ctx) =>
                  ` $${ctx.parsed.y.toLocaleString("en-US", { minimumFractionDigits: 2 })}`,
              },
            },
          },
          scales: {
            y: {
              beginAtZero: false,
              grid: { color: "rgba(0,0,0,0.04)" },
              ticks: {
                callback: (v) =>
                  "$" + (v >= 1000 ? (v / 1000).toFixed(0) + "k" : v),
              },
            },
            x: { grid: { display: false } },
          },
        },
      });
    },

    async addSnapshot() {
      const body = {
        account_id: parseInt(this.snapForm.account_id),
        balance: parseFloat(this.snapForm.balance),
      };
      if (this.snapForm.snapshot_date)
        body.snapshot_date = this.snapForm.snapshot_date;
      await api.post("/api/net-worth/snapshot", body);
      this.showSnapForm = false;
      this.snapForm = { account_id: "", balance: "", snapshot_date: "" };
      await this.load();
    },

    async addAccount() {
      await api.post("/api/net-worth/accounts", this.acctForm);
      this.showAcctForm = false;
      this.acctForm = { name: "", type: "checking", institution: "" };
      await this.load();
    },

    get assets() {
      return (this.latest?.accounts ?? []).filter((a) => (a.balance ?? 0) > 0);
    },
    get liabilities() {
      return (this.latest?.accounts ?? []).filter((a) => (a.balance ?? 0) < 0);
    },
    get totalAssets() {
      return this.assets.reduce((s, a) => s + (a.balance ?? 0), 0);
    },
    get totalLiabilities() {
      return this.liabilities.reduce((s, a) => s + (a.balance ?? 0), 0);
    },

    fmt,
    fmtAbs,
  };
}

/* ── AI Query ───────────────────────────────────────────────────────────── */
function aiApp() {
  return {
    question: "",
    result: null,
    loading: false,
    history: [],

    suggestions: [
      "How much did I spend on food last month?",
      "What are my top 5 merchants this month?",
      "Show my income vs expenses for 3 months",
      "Am I over budget anywhere?",
      "What's my biggest spending category?",
    ],

    async ask() {
      if (!this.question.trim()) return;
      const q = this.question;
      this.loading = true;
      this.result = null;
      this.question = "";
      try {
        const res = await api.post("/api/ai/query", { question: q });
        this.result = res;
        this.history.unshift({
          q,
          a: res.answer,
          source: res.source,
          data: res.data,
        });
      } catch (e) {
        this.result = { answer: "Error: " + e.message, source: "error" };
      }
      this.loading = false;
    },

    useSuggestion(s) {
      this.question = s;
      this.ask();
    },
  };
}

/* ── Recurring Transactions ─────────────────────────────────────────────── */
function recurringApp() {
  return {
    items: [],
    loading: false,
    detecting: false,
    detectMsg: "",
    showDismissed: false,
    editingId: null,
    editForm: {},

    FREQ_LABELS: {
      weekly: "Weekly",
      biweekly: "Every 2 weeks",
      monthly: "Monthly",
      annual: "Annual",
      irregular: "Irregular",
    },

    async init() {
      await this.load();
    },

    async load() {
      this.loading = true;
      try {
        this.items = await api.get(
          `/api/recurring?include_dismissed=${this.showDismissed}`,
        );
      } catch (e) {
        console.error(e);
      }
      this.loading = false;
    },

    async detect() {
      this.detecting = true;
      this.detectMsg = "";
      try {
        const res = await api.post("/api/recurring/detect", {});
        this.detectMsg = res.message;
        await this.load();
      } catch (e) {
        this.detectMsg = "Error: " + e.message;
      }
      this.detecting = false;
    },

    async confirm(item) {
      await api.patch(`/api/recurring/${item.id}`, { status: "confirmed" });
      item.status = "confirmed";
    },

    async dismiss(item) {
      await api.patch(`/api/recurring/${item.id}`, { status: "dismissed" });
      await this.load();
    },

    startEdit(item) {
      this.editingId = item.id;
      this.editForm = {
        amount: item.amount,
        frequency: item.frequency,
        notes: item.notes || "",
        next_expected_date: item.next_expected_date || "",
      };
    },

    async saveEdit(item) {
      const body = {
        amount: parseFloat(this.editForm.amount),
        frequency: this.editForm.frequency,
        notes: this.editForm.notes || null,
        next_expected_date: this.editForm.next_expected_date || null,
      };
      const updated = await api.patch(`/api/recurring/${item.id}`, body);
      Object.assign(item, updated);
      this.editingId = null;
    },

    async remove(item) {
      if (!confirm(`Remove "${item.merchant_clean}" from recurring?`)) return;
      await api.del(`/api/recurring/${item.id}`);
      await this.load();
    },

    get expenses() {
      return this.items.filter((i) => !i.is_income);
    },
    get income() {
      return this.items.filter((i) => i.is_income);
    },

    get monthlyExpenseTotal() {
      return this.expenses.reduce(
        (s, i) => s + this._toMonthly(i.amount, i.frequency),
        0,
      );
    },
    get monthlyIncomeTotal() {
      return this.income.reduce(
        (s, i) => s + this._toMonthly(i.amount, i.frequency),
        0,
      );
    },

    _toMonthly(amount, freq) {
      const map = {
        weekly: 4.33,
        biweekly: 2.17,
        monthly: 1,
        annual: 1 / 12,
        irregular: 1,
      };
      return amount * (map[freq] ?? 1);
    },

    daysUntil(dateStr) {
      if (!dateStr) return null;
      return Math.ceil((new Date(dateStr) - new Date()) / 86400000);
    },

    dueSoonClass(dateStr) {
      const d = this.daysUntil(dateStr);
      if (d === null) return "";
      if (d <= 3) return "amount-expense";
      if (d <= 7) return "text-amber";
      return "text-muted";
    },

    dueSoonLabel(dateStr) {
      const d = this.daysUntil(dateStr);
      if (d === null) return "—";
      if (d < 0) return "Overdue";
      if (d === 0) return "Today";
      if (d === 1) return "Tomorrow";
      return `In ${d} days`;
    },

    statusBadge(status) {
      return (
        {
          detected: "badge badge-warning",
          confirmed: "badge badge-ok",
          dismissed: "badge",
        }[status] || "badge"
      );
    },

    fmtAbs,
    fmt,
  };
}

/* ── Cashflow Forecast ──────────────────────────────────────────────────── */
function forecastApp() {
  return {
    forecast: null,
    loading: false,
    days: 90,
    chart: null,

    async init() {
      await this.load();
    },

    async load() {
      this.loading = true;
      try {
        this.forecast = await api.get(
          `/api/recurring/forecast?days=${this.days}&include_detected=true`,
        );
        this.$nextTick(() => this.renderChart());
      } catch (e) {
        console.error(e);
      }
      this.loading = false;
    },

    renderChart() {
      const el = document.getElementById("forecastChart");
      if (!el || el.offsetParent === null || !this.forecast) return;
      if (this.chart) this.chart.destroy();

      const daily = this.forecast.daily;
      const labels = daily.map((d) => d.date);
      const balances = daily.map((d) => d.running_balance);
      const eventDates = new Set(this.forecast.events.map((e) => e.date));

      this.chart = new Chart(el, {
        type: "line",
        data: {
          labels,
          datasets: [
            {
              label: "Projected Cash Flow",
              data: balances,
              borderColor: "#16a34a",
              segment: {
                borderColor: (ctx) =>
                  ctx.p1.parsed.y >= 0 ? "#16a34a" : "#dc2626",
              },
              backgroundColor: (ctx) => {
                const chart = ctx.chart;
                const { ctx: canvasCtx, chartArea } = chart;
                if (!chartArea) return "transparent";
                const g = canvasCtx.createLinearGradient(
                  0,
                  chartArea.top,
                  0,
                  chartArea.bottom,
                );
                g.addColorStop(0, "rgba(22,163,74,0.12)");
                g.addColorStop(0.5, "rgba(22,163,74,0.03)");
                g.addColorStop(1, "rgba(220,38,38,0.06)");
                return g;
              },
              fill: true,
              tension: 0.3,
              pointRadius: (ctx) =>
                eventDates.has(labels[ctx.dataIndex]) ? 4 : 0,
              pointHoverRadius: 6,
              borderWidth: 2,
            },
          ],
        },
        options: {
          plugins: {
            legend: { display: false },
            tooltip: {
              callbacks: {
                title: ([ctx]) => {
                  const d = new Date(ctx.label);
                  return d.toLocaleDateString("en-US", {
                    weekday: "short",
                    month: "short",
                    day: "numeric",
                  });
                },
                label: (ctx) =>
                  ` Net flow: ${ctx.parsed.y >= 0 ? "+" : ""}$${ctx.parsed.y.toFixed(2)}`,
                afterBody: (items) => {
                  const dateStr = items[0]?.label;
                  const eventsOnDay = (this.forecast?.events ?? []).filter(
                    (e) => e.date === dateStr,
                  );
                  if (!eventsOnDay.length) return [];
                  return [
                    "",
                    ...eventsOnDay.map(
                      (e) =>
                        `${e.is_income ? "↑" : "↓"} ${e.merchant} $${e.amount.toFixed(2)}`,
                    ),
                  ];
                },
              },
            },
          },
          scales: {
            y: {
              grid: { color: "rgba(0,0,0,0.04)" },
              ticks: {
                callback: (v) =>
                  (v >= 0 ? "+" : "") + "$" + Math.abs(v).toLocaleString(),
              },
            },
            x: {
              grid: { display: false },
              ticks: {
                maxTicksLimit: 12,
                callback: function (val) {
                  const d = new Date(this.getLabelForValue(val));
                  return d.toLocaleDateString("en-US", {
                    month: "short",
                    day: "numeric",
                  });
                },
              },
            },
          },
          interaction: { mode: "index", intersect: false },
        },
      });
    },

    get upcomingBills() {
      return (this.forecast?.upcoming_bills ?? []).slice(0, 8);
    },
    get monthlySummary() {
      return this.forecast?.monthly_summary ?? [];
    },
    get totalProjectedExpenses() {
      return this.monthlySummary.reduce((s, m) => s + m.expenses, 0);
    },
    get totalProjectedIncome() {
      return this.monthlySummary.reduce((s, m) => s + m.income, 0);
    },

    formatDate(dateStr) {
      if (!dateStr) return "—";
      return new Date(dateStr).toLocaleDateString("en-US", {
        month: "short",
        day: "numeric",
      });
    },

    daysUntil(dateStr) {
      if (!dateStr) return null;
      return Math.ceil((new Date(dateStr) - new Date()) / 86400000);
    },

    dueSoonLabel(dateStr) {
      const d = this.daysUntil(dateStr);
      if (d === null) return "—";
      if (d < 0) return "Overdue";
      if (d === 0) return "Today";
      if (d === 1) return "Tomorrow";
      return `${d}d`;
    },

    urgencyClass(dateStr) {
      const d = this.daysUntil(dateStr);
      if (d === null) return "text-muted";
      if (d <= 3) return "amount-expense";
      if (d <= 7) return "text-amber";
      return "text-muted";
    },

    fmtAbs,
    fmt,
  };
}
