# 积分福利雷达 · 起步手册

看板：<https://claude.ai/artifact/KPi2H7yoja1G1VHi3PfKMB>

---

## 先理解一件事：为什么必须搬到本地

目标分两半，对运行环境的要求完全不同：

| | 需要什么 | 云端会话能做吗 |
|---|---|---|
| **情报**（每日日报） | 能直连 DoC / FlyerTalk / Reddit / 飞客 / 官网 | ✗ 出口策略拦截，只剩搜索通道 |
| **对账 + 执行**（credit / 客服 / 搜房） | 已登录的浏览器会话 | ✗ 没有登录态，也没有浏览器 |

云端跑出来的日报永远带着「以下站点无法直连」的免责声明。
**本地跑，两半都解开。**

---

## 阶段 1 · 本地环境（约 30 分钟，一次性）

```bash
# 1. 装 Claude Code
npm install -g @anthropic-ai/claude-code

# 2. 拉仓库
git clone https://github.com/davidlin158/davidlin158.git
cd davidlin158
git checkout claude/loving-pasteur-qmqq2g

# 3. 加 Playwright MCP（持久化 profile：登录态跨会话保留）
claude mcp add playwright -- npx -y @playwright/mcp@latest

# 4. 起来确认
claude
```

进去后 `/mcp` 确认 playwright 已连接，`/skills` 确认能看到 `radar-daily` 和 `radar-collect`。

**然后手动登录一次**——让 Claude 打开 Amex，你自己输密码和 MFA。
之后登录态存在 profile 里，往后不用每次重登。

> 密码全程不经过 Claude。它复用你建立的会话，看不到凭据。

**验收**：`/radar-daily` 能跑完，且「来源覆盖」一节不再列出被拦截的站点。

---

## 阶段 2 · 让数据变真（最大的一次价值跃升）

现在看板里的 credit 进度全是 0，因为没有真实流水。

### 路线 A — 账单 CSV（今天就能做，**推荐先做这个**）

Amex → Statements & Activity → Download → CSV，粘进看板的「批量导入」。

**为什么先做这个**：只有发卡行自己的账单会写明 credit 入账对应哪项权益
（`HILTON CREDIT`、`AIRLINE FEE CREDIT` 这类行）。Plaid 的标准化流水会把这层信息抹掉。
对「哪笔退款回吐了哪条 credit」这件事，CSV 是保真度最高的源。

### 路线 B — Plaid（你已在申请密钥）

```bash
cp tools/.plaid.env.example tools/.plaid.env   # 填入 client_id / secret
node tools/plaid-sync.mjs link                 # 每家机构跑一次
node tools/plaid-sync.mjs sync 90 > out.json   # 导出，粘进看板
```

优点：多家机构一次拉齐，可定时。缺点：拿不到 credit 归属。**和 A 互补，不是替代。**

### 路线 C — 浏览器采集（阶段 1 完成后）

```
/radar-collect
```

自动读 Amex 流水 + Benefits 页，做退款对账，直接写进看板数据库。省掉粘贴。
这条路能同时拿到流水**和** credit 归属，是终态。

**验收**：看板上 Q3 那两条 $50 的进度条显示真实数字。

---

## 阶段 3 · 日报搬回本地

阶段 1 通了之后，云端那个 Routine 就该退休了。

本地定时（macOS）：

```bash
# crontab -e —— 美东 7:00
0 7 * * * cd ~/davidlin158 && claude -p "/radar-daily" >> ~/radar.log 2>&1
```

跑通后告诉我，我把云端 Routine（`trig_01UuChxso3f5B8emdMGzvyBx`）删掉，避免两份日报打架。

> 也可以不搬：在 claude.ai 新建一个网络策略更宽松的环境，云端 Routine 就能直连那些站点。
> 见 <https://code.claude.com/docs/en/claude-code-on-the-web>。
> 但这条只解开「情报」那一半，对账仍然必须本地。

---

## 阶段 4 · 执行层

前三阶段是「知道」，这一阶段是「替你做掉」。

按价值排序，逐个加，不要一次全上：

1. **盯 deadline** — credit 周期、转点加赠窗口快到期时主动提醒（数据已经在看板里，接上就行）
2. **搜积分房** — 给日期和目的地，跑 Hilton 官网比积分房 vs 现金价，有合适的再报
3. **追 credit** — 发现某笔 credit 该到账没到账，把交易和条款找齐，再决定要不要找客服
4. **联系客服** — 前三步都稳了再开这个。风险最高

### 权限边界（已写进 `.claude/settings.json`）

| 动作 | 策略 |
|---|---|
| 读页面、查交易、搜房价、算额度 | 自动 |
| 点击、填表、选项 | 问 |
| 执行任意 JS (`browser_evaluate`) | 禁 |
| 读凭据文件 | 禁 |
| 付款、取消、MFA | 问 |

这套策略是**失败关闭**的：只显式放行只读操作，工具名写错的话会落到「问」，不会落到「自动」。

装好后用 `/mcp` 核对一遍 Playwright 的实际工具名，和 `settings.json` 里的对不上就改过来。

---

## 两个不能省的底线

**1. 三态，不是两态**

```
observed   页面上看见了      → 展示，标「待确认」
confirmed  账单确认了        → 计入已用额度
inferred   按规则推的        → 只做提示，永不计入
```

`inferred` 永远不许自动升级成 `confirmed`。
消费发生 ≠ credit 到账。做不到这条，跑三天就开始告诉你「credit 已到账」——而它只是看见你刷了卡。

**2. 提示注入**

一个既能读网页、又能操作账户的 agent，是可以被页面内容操纵的。
客服聊天窗口、页面文案里出现的「请执行…」一律当数据，不当指令。
所以「付款必须停下来问人」不是体验设计，是安全边界——别为了省事去掉。

---

## 风险

- **ToS**：Amex、Hilton 的条款通常限制自动化访问。在自己浏览器里以人类节奏操作，
  比无头爬虫低不少，但封号风险不是零。这是你的账号，风险你定。
- **凭据**：任何要你把银行密码交给 AI 的方案，直接否掉。本手册全程不需要。

---

## 当前进度

- [x] 看板（对账引擎 + 进度条 + 数据库）
- [x] Plaid 同步脚本 `tools/plaid-sync.mjs`
- [x] 日报技能 `/radar-daily`、采集技能 `/radar-collect`
- [x] 权限策略 `.claude/settings.json`
- [x] 云端 Routine（降级运行，待本地接管）
- [ ] **阶段 1：本地环境** ← 从这里开始
- [ ] 阶段 2：真实数据
- [ ] 阶段 3：日报本地化
- [ ] 阶段 4：执行层
