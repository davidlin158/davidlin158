#!/usr/bin/env node
/**
 * plaid-sync — 把 Plaid 连接的银行/信用卡交易导出成「积分福利雷达」可直接导入的 JSON。
 *
 * 为什么需要它：claude.ai 目录里的 "Plaid Developer Tools" 连接器是给开发者
 * 排查自己 Plaid 集成用的（usage / Link 转化率 / item 诊断），读不到你本人的
 * 账户流水。要拿到真实交易，只能用你自己的 Plaid app 调 /transactions。
 *
 * 用法：
 *   1) 在 https://dashboard.plaid.com 建一个 app，拿到 client_id / secret
 *   2) 写进 tools/.plaid.env（见 .plaid.env.example），该文件已被 gitignore
 *   3) node tools/plaid-sync.mjs link          # 浏览器里绑定一家机构，存下 access_token
 *      （每家机构跑一次：Amex、Citi、BofA、RBC…）
 *   4) node tools/plaid-sync.mjs sync 90       # 导出最近 90 天，stdout 输出 JSON
 *      node tools/plaid-sync.mjs sync 90 > out.json
 *   5) 把 JSON 粘进雷达页面的「批量导入」
 *
 * 输出格式：[{ date:"2026-09-12", merchant:"HILTON WAIKOLOA", amount:412.8, account:"Amex Biz Plat" }]
 * 金额沿用 Plaid 符号约定：正数=支出，负数=退款/入账 —— 雷达页面据此判定 charge / refund。
 */

import { createServer } from "node:http";
import { readFileSync, writeFileSync, existsSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const HERE = dirname(fileURLToPath(import.meta.url));
const ENV_FILE = join(HERE, ".plaid.env");
const TOKEN_FILE = join(HERE, ".plaid-tokens.json");
const PORT = 842;

/* ---------- config ---------- */

function loadEnv() {
  if (existsSync(ENV_FILE)) {
    for (const line of readFileSync(ENV_FILE, "utf8").split(/\r?\n/)) {
      const m = line.match(/^\s*([A-Z_]+)\s*=\s*(.*)\s*$/);
      if (m && !process.env[m[1]]) process.env[m[1]] = m[2].replace(/^["']|["']$/g, "");
    }
  }
  const { PLAID_CLIENT_ID, PLAID_SECRET } = process.env;
  const env = process.env.PLAID_ENV || "production";
  if (!PLAID_CLIENT_ID || !PLAID_SECRET) {
    die(`缺少 PLAID_CLIENT_ID / PLAID_SECRET。\n请复制 tools/.plaid.env.example 为 tools/.plaid.env 并填入，或用环境变量传入。`);
  }
  return { clientId: PLAID_CLIENT_ID, secret: PLAID_SECRET, base: `https://${env}.plaid.com` };
}

const die = msg => { console.error("\n✗ " + msg + "\n"); process.exit(1); };

async function plaid(cfg, path, body) {
  const res = await fetch(cfg.base + path, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ client_id: cfg.clientId, secret: cfg.secret, ...body }),
  });
  const json = await res.json().catch(() => ({}));
  if (!res.ok) {
    die(`Plaid ${path} 返回 ${res.status}：${json.error_code || ""} ${json.error_message || JSON.stringify(json)}`);
  }
  return json;
}

const readTokens = () => (existsSync(TOKEN_FILE) ? JSON.parse(readFileSync(TOKEN_FILE, "utf8")) : []);
const writeTokens = t => writeFileSync(TOKEN_FILE, JSON.stringify(t, null, 2) + "\n", { mode: 0o600 });

/* ---------- link：绑定一家机构 ---------- */

async function cmdLink(cfg) {
  const { link_token } = await plaid(cfg, "/link/token/create", {
    user: { client_user_id: "radar-local" },
    client_name: "积分福利雷达",
    products: ["transactions"],
    country_codes: ["US", "CA"],
    language: "en",
  });

  const page = `<!doctype html><meta charset="utf-8"><title>绑定账户</title>
<style>body{font:15px/1.6 system-ui,-apple-system,"PingFang SC",sans-serif;display:grid;place-items:center;height:100vh;margin:0;background:#F5F7F5;color:#14202A}
.b{background:#fff;padding:32px 36px;border-radius:4px;box-shadow:0 6px 24px rgba(0,0,0,.08);max-width:420px;text-align:center}
code{background:#EDF1EF;padding:2px 6px;border-radius:2px;font-size:13px}</style>
<div class="b"><h2 style="margin:0 0 8px">绑定账户</h2>
<p id="s">正在打开 Plaid Link…</p></div>
<script src="https://cdn.plaid.com/link/v2/stable/link-initialize.js"></script>
<script>
Plaid.create({
  token: ${JSON.stringify(link_token)},
  onSuccess: (public_token, meta) => {
    fetch("/done", { method:"POST", headers:{"Content-Type":"application/json"},
      body: JSON.stringify({ public_token, institution: meta.institution && meta.institution.name }) })
      .then(() => { document.getElementById("s").innerHTML = "✓ 绑定成功，可以关掉这个页面，回到终端。"; });
  },
  onExit: (err) => {
    document.getElementById("s").textContent = err ? ("已退出：" + (err.display_message || err.error_message)) : "已取消。";
    fetch("/abort", { method: "POST" });
  },
}).open();
</script>`;

  await new Promise(resolve => {
    const server = createServer((req, res) => {
      if (req.method === "GET" && req.url === "/") {
        res.writeHead(200, { "Content-Type": "text/html; charset=utf-8" });
        return res.end(page);
      }
      if (req.method === "POST" && req.url === "/done") {
        let raw = "";
        req.on("data", c => (raw += c));
        return req.on("end", async () => {
          const { public_token, institution } = JSON.parse(raw);
          const { access_token, item_id } = await plaid(cfg, "/item/public_token/exchange", { public_token });
          const tokens = readTokens().filter(t => t.item_id !== item_id);
          tokens.push({ item_id, access_token, institution: institution || "(未知机构)", added: new Date().toISOString() });
          writeTokens(tokens);
          console.log(`✓ 已保存：${institution || item_id} → ${TOKEN_FILE}`);
          res.writeHead(204).end();
          server.close(resolve);
        });
      }
      if (req.method === "POST" && req.url === "/abort") {
        res.writeHead(204).end();
        return server.close(resolve);
      }
      res.writeHead(404).end();
    });
    server.listen(PORT, () => console.log(`\n→ 在浏览器打开 http://localhost:${PORT} 完成绑定（完成后本进程自动退出）\n`));
  });
}

/* ---------- sync：导出交易 ---------- */

async function cmdSync(cfg, days) {
  const tokens = readTokens();
  if (!tokens.length) die(`还没有绑定任何机构。先跑：node tools/plaid-sync.mjs link`);

  const end = new Date();
  const start = new Date(end.getTime() - days * 86400000);
  const iso = d => d.toISOString().slice(0, 10);
  const out = [];

  for (const t of tokens) {
    const accounts = {};
    let offset = 0, total = Infinity;
    while (offset < total) {
      const page = await plaid(cfg, "/transactions/get", {
        access_token: t.access_token,
        start_date: iso(start),
        end_date: iso(end),
        options: { count: 500, offset },
      });
      total = page.total_transactions;
      for (const a of page.accounts) accounts[a.account_id] = a.name || a.official_name || a.mask;
      for (const tx of page.transactions) {
        if (tx.pending) continue;
        out.push({
          date: tx.date,
          merchant: tx.merchant_name || tx.name,
          amount: tx.amount,                       // 正=支出，负=退款/入账
          account: `${t.institution} · ${accounts[tx.account_id] || ""}`.trim(),
        });
      }
      offset += page.transactions.length;
      if (!page.transactions.length) break;
    }
    console.error(`  ${t.institution}: 累计 ${out.length} 笔`);
  }

  out.sort((a, b) => a.date.localeCompare(b.date));
  console.error(`\n✓ ${iso(start)} → ${iso(end)}，共 ${out.length} 笔。以下 JSON 可直接粘进雷达页面的「批量导入」：\n`);
  console.log(JSON.stringify(out, null, 2));
}

/* ---------- main ---------- */

const [cmd, arg] = process.argv.slice(2);
const cfg = loadEnv();

if (cmd === "link") await cmdLink(cfg);
else if (cmd === "sync") await cmdSync(cfg, Number(arg) > 0 ? Number(arg) : 90);
else {
  console.log(`用法:
  node tools/plaid-sync.mjs link          绑定一家机构（每家跑一次）
  node tools/plaid-sync.mjs sync [天数]   导出交易 JSON，默认 90 天

已绑定：${readTokens().map(t => t.institution).join("、") || "（无）"}`);
}
