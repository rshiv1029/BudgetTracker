// ── Utility ────────────────────────────────────────────────────────────────

const api = {
  async get(path) {
    const r = await fetch(path);
    if (!r.ok) {
      throw new Error("GET ${path} failed: ${r.status} ${r.statusText}");
    }
    return r.json();
  },
  async post(path, body) {
    const r = await fetch(path, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify(body),
    });
    if (!r.ok) {
      throw new Error("POST ${path} failed: ${r.status} ${r.statusText}");
    }
    return r.json();
  },
  async postForm(path, formData) {
    const r = await fetch(path, {
      method: "POST",
      body: formData,
    });
    if (!r.ok) {
      const txt = await r.text();
      throw new Error(
        "POST ${path} failed: ${r.status} ${r.statusText} - ${txt}",
      );
    }
    return r.json();
  },
  async patch(path, body) {
    const r = await fetch(path, {
      method: "PATCH",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify(body),
    });
    if (!r.ok) {
      throw new Error("PATCH ${path} failed: ${r.status} ${r.statusText}");
    }
    return r.json();
  },
  async del(path) {
    const r = await fetch(path, {
      method: "DELETE",
    });
    if (!r.ok) {
      throw new Error("DELETE ${path} failed: ${r.status} ${r.statusText}");
    }
  },
};

function fmt(amount) {
  const abs = Math.abs(amount);
  const str = abs.toLocaleString("en-US", {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  });
  return amount < 0 ? `-$${str}` : `$${str}`;
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

function currentMonthYear() {
  const d = new Date();
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}`;
}

// Root App

function financeApp() {
  return {
    page: "dashboard",
    navigate(p) {
      this.page = p;
    },
  };
}

// ── Dashboard ─────────────────────────────────────────────────────────────────

function dashboardApp() {
  return {
    insights: null,
    budgetStatus: [],
    loading: true,
    charts: {},

    async init() {
      this.loading = true;
      try {
        const [ins, budgets] = await Promise.all([
          api.get("/api/ai/insights?months=3"),
          api.get(`/api/budgets/status?month_year=${currentMonthYear()}`),
        ]);
        this.insights = ins;
        this.budgetStatus = budgets;
        this.$nextTick(() => this.renderCharts());
      } catch (e) {
        console.error(e);
      }
      this.loading = false;
    },

    get totalIncome() {
      if (!this.insights) return 0;
      const rows = this.insights.income_vs_expenses;
      if (!rows.length) return 0;
      const last = rows[rows.length - 1];
      return last.income;
    },
    get totalExpenses() {
      if (!this.insights) return 0;
      const rows = this.insights.income_vs_expenses;
      if (!rows.length) return 0;
      const last = rows[rows.length - 1];
      return last.expenses;
    },
    get netThisMonth() {
      return this.totalIncome - this.totalExpenses;
    },
    renderCharts() {
      // Destroy old charts
      Object.values(this.charts).forEach((c) => c.destroy());
      this.charts = {};

      if (this.insights) {
        this.renderCategoryPie();
        this.renderIncomeBar();
      }
    },

    renderCategoryPie() {
      const el = document.getElementById("catPieChart");
      if (!el) return;
      const data = this.insights.category_breakdown.slice(0, 8);
      this.charts.pie = new Chart(el, {
        type: "doughnut",
        data: {
          labels: data.map((r) => r.category),
          datasets: [
            {
              data: data.map((r) => r.total),
              backgroundColor: [
                "#f97316",
                "#3b82f6",
                "#8b5cf6",
                "#ec4899",
                "#10b981",
                "#f59e0b",
                "#06b6d4",
                "#94a3b8",
              ],
            },
          ],
        },
        options: { plugins: { legend: { position: "right" } }, cutout: "60%" },
      });
    },

    renderIncomeBar() {
      const el = document.getElementById("incomeBarChart");
      if (!el) return;
      const data = this.insights.income_vs_expenses;
      this.charts.bar = new Chart(el, {
        type: "bar",
        data: {
          labels: data.map((r) => r.month),
          datasets: [
            {
              label: "Income",
              data: data.map((r) => r.income),
              backgroundColor: "#22c55e",
            },
            {
              label: "Expenses",
              data: data.map((r) => r.expenses),
              backgroundColor: "#f97316",
            },
          ],
        },
        options: {
          plugins: { legend: { position: "top" } },
          scales: { y: { beginAtZero: true } },
        },
      });
    },
    barWidth(pct) {
      return Math.min(pct * 100, 100) + "%";
    },
    barClass(status) {
      return `bar-${status}`;
    },
    statusClass(status) {
      return `status-${status}`;
    },
  };
}

// ── Transactions ──────────────────────────────────────────────────────────────

function transactionsApp() {
  return {
    transactions: [],
    categories: [],
    loading: false,
    filters: { month_year: currentMonthYear(), category: "", search: "" },
    editingId: null,
    editCategory: "",

    async init() {
      this.categories = await api.get("/api/transactions/categories");
      await this.load();
    },

    async load() {
      this.loading = true;
      const params = new URLSearchParams();
      if (this.filters.month_year)
        params.set("month_year", this.filters.month_year);
      if (this.filters.category) params.set("category", this.filters.category);
      if (this.filters.search) params.set("search", this.filters.search);
      params.set("limit", "500");
      this.transactions = await api.get(`/api/transactions?${params}`);
      this.loading = false;
    },
    startEdit(txn) {
      this.editingId = txn.id;
      this.editCategory = txn.category;
    },

    async saveEdit(txn) {
      await api.patch(`/api/transactions/${txn.id}`, {
        category: this.editCategory,
      });
      txn.category = this.editCategory;
      this.editingId = null;
    },

    cancelEdit() {
      this.editingId = null;
    },

    amountClass(amount) {
      return amount < 0 ? "amount-expense" : "amount-income";
    },

    get totalExpenses() {
      return this.transactions
        .filter((t) => t.amount < 0)
        .reduce((s, t) => s + Math.abs(t.amount), 0);
    },
    get totalIncome() {
      return this.transactions
        .filter((t) => t.amount > 0)
        .reduce((s, t) => s + t.amount, 0);
    },
    fmt,
    fmtAbs,
  };
}

// ── Accounts (Plaid) ──────────────────────────────────────────────────────────

function accountsApp() {
  return {
    items: [],
    status: null,
    loading: false,
    syncing: false,
    syncResults: null,
    error: null,

    async init() {
      await this.load();
    },

    async load() {
      const [items, status] = await Promise.all([
        api.get("/api/plaid/items"),
        api.get("/api/plaid/status"),
      ]);
      this.items = items;
      this.status = status;
    },

    async connectBank() {
      this.error = null;
      if (!this.status || !this.status.configured) {
        this.error =
          "Plaid credentials not configured. Add PLAID_CLIENT_ID and PLAID_SECRET to your .env file and restart the server.";
        return;
      }
      try {
        const { link_token } = await api.post("/api/plaid/link-token", {});
        this._openLink(link_token);
      } catch (e) {
        this.error = e.message;
      }
    },

    _openLink(linkToken) {
      const handler = Plaid.create({
        token: linkToken,
        onSuccess: async (publicToken, metadata) => {
          try {
            this.syncing = true;
            const result = await api.post("/api/plaid/exchange-token", {
              public_token: publicToken,
              institution_name: metadata.institution?.name || "Unknown Bank",
              institution_id: metadata.institution?.institution_id || "",
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
      if (!confirm(`Disconnect ${name}? Existing transactions will be kept.`))
        return;
      await api.del(`/api/plaid/items/${itemId}`);
      await this.load();
    },
  };
}

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
      Object.entries(this.form).forEach(([k, v]) => fd.append(k, v));

      try {
        this.result = await api.postForm("/api/transactions/import", fd);
      } catch (e) {
        this.error = e.message;
      }
      this.loading = false;
    },
  };
}

// ── Budgets ───────────────────────────────────────────────────────────────────

function budgetsApp() {
  return {
    rules: [],
    status: [],
    categories: [],
    month_year: currentMonthYear(),
    form: {
      category: "",
      month_year: null,
      limit_amount: "",
      alert_threshold: 0.8,
    },
    showForm: false,
    editId: null,

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
    },

    async save() {
      const body = {
        ...this.form,
        limit_amount: parseFloat(this.form.limit_amount),
      };
      if (!body.month_year) body.month_year = null;
      if (this.editId) {
        (await api.patch) ? null : null; // handled via PUT
        await fetch(`/api/budgets/${this.editId}`, {
          method: "PUT",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(body),
        });
      } else {
        await api.post("/api/budgets", body);
      }
      this.showForm = false;
      this.editId = null;
      this.form = {
        category: "",
        month_year: null,
        limit_amount: "",
        alert_threshold: 0.8,
      };
      await this.load();
    },

    async remove(id) {
      await api.del(`/api/budgets/${id}`);
      await this.load();
    },

    startEdit(rule) {
      this.editId = rule.id;
      this.form = { ...rule, limit_amount: String(rule.limit_amount) };
      this.showForm = true;
    },

    barWidth(pct) {
      return Math.min(pct * 100, 100) + "%";
    },
    barClass(s) {
      return `bar-${s}`;
    },
    statusClass(s) {
      return `status-${s}`;
    },
    fmtAbs,
  };
}

// ── Net Worth ─────────────────────────────────────────────────────────────────

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
      if (!el || !this.history.length) return;
      if (this.chart) this.chart.destroy();
      this.chart = new Chart(el, {
        type: "line",
        data: {
          labels: this.history.map((r) => r.snapshot_date),
          datasets: [
            {
              label: "Net Worth",
              data: this.history.map((r) => r.total),
              borderColor: "#3b82f6",
              backgroundColor: "rgba(59,130,246,0.08)",
              fill: true,
              tension: 0.3,
            },
          ],
        },
        options: {
          plugins: { legend: { display: false } },
          scales: { y: { beginAtZero: false } },
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

    fmt,
  };
}

// ── AI Query ──────────────────────────────────────────────────────────────────

function aiApp() {
  return {
    question: "",
    result: null,
    loading: false,
    history: [],

    async ask() {
      if (!this.question.trim()) return;
      this.loading = true;
      this.result = null;
      try {
        const res = await api.post("/api/ai/query", {
          question: this.question,
        });
        this.result = res;
        this.history.unshift({
          q: this.question,
          a: res.answer,
          source: res.source,
        });
        this.question = "";
      } catch (e) {
        this.result = { answer: "Error: " + e.message, source: "error" };
      }
      this.loading = false;
    },

    suggestions: [
      "How much did I spend on food last month?",
      "What are my top 5 merchants this month?",
      "Show income vs expenses for the last 3 months",
      "What unusual spending patterns do you see?",
    ],

    useSuggestion(s) {
      this.question = s;
      this.ask();
    },
  };
}
