# F1 一手素材采集器

把 FIA 决策文件、FIA 新闻、F1 官网文章、外媒 RSS 定时抓下来，
落成本地档案库（PDF 原文 + 抽取的正文 + 每日摘要）。

**核心思路：抓取动作放在墙外，人在国内只负责看结果。**

---

## 为什么这样做

你不需要翻墙。GitHub Actions 是 GitHub 的服务器在跑，它在墙外，
访问 fia.com、formula1.com 没有任何问题。它抓完把文件提交回仓库，
你在国内打开仓库页面就能看。

三个额外好处：

- **免费**。公开仓库每月 2000 分钟，这个任务一次跑 1–2 分钟。
- **不需要服务器**。不用买 VPS、不用维护。
- **有历史**。每次抓的都 commit，形成一个可检索的档案库，
  三个月后这就是别人没有的资产。

---

## 部署（约 20 分钟，一次性）

### 1. 建仓库

打开 GitHub，新建一个 **Public** 仓库，名字随便，比如 `f1-archive`。

> 必须是 Public，Private 仓库的 Actions 也免费但有额度限制，
> 而且 Public 才能无限跑。

### 2. 上传本目录

把这个 `collector/` 目录里的所有内容（**包括 `.github` 这个隐藏文件夹**）
上传到仓库根目录。网页上传时注意要传 `.github/workflows/collect.yml`。

上传后的结构应该是：

```
你的仓库/
├── collect.py
├── README.md
└── .github/
    └── workflows/
        └── collect.yml
```

### 3. 开启 Actions

仓库页面 → **Settings → Actions → General** → 选 **Allow all actions** → Save。

然后点 **Actions** 标签页，左边选「F1 一手素材采集」，
右边点 **Run workflow** 手动跑一次。

第一次跑会下载较多历史 PDF（`--limit 30`，每个源最多 30 条），
大概 2–5 分钟。之后每次只抓新增，很快。

### 4. （可选）配机器人推送

想每天在手机上直接收到摘要，配一个 webhook：

- **飞书**：群设置 → 群机器人 → 添加「自定义机器人」→ 复制 Webhook 地址
- **企业微信**：群设置 → 群机器人 → 添加 → 复制 Webhook 地址
- **钉钉**：群设置 → 智能群助手 → 添加机器人 → 自定义 → 复制 Webhook

然后到仓库 **Settings → Secrets and variables → Actions → New repository secret**：

- Name：`WEBHOOK_URL`
- Secret：粘贴刚才复制的地址

`collect.py` 会自动识别是飞书、钉钉还是企业微信，用对应的格式推送。
没配也能用，只是不推送。

---

## 抓什么

| 源 | 内容 | 类型 |
|---|---|---|
| `fia-decisions` | 赛事干事决定、传唤、车检、罚单全文 | PDF（自动抽正文） |
| `fia-news` | FIA 官方新闻、**发布会逐字稿** | 网页 |
| `f1-latest` | F1 官网最新文章 | 网页 |
| `the-race` | The Race RSS | RSS |
| `motorsport` | Motorsport.com F1 RSS | RSS |

FIA 决策文件这个源会自动找**最新赛季**的页面（默认停在上一季，
脚本里有处理），所以不用每年改代码。

---

## 输出结构

```
archive/
├── latest.md                         ← 每次运行后更新，先看这个
├── digest-2026-11-02.md              ← 按天归档的摘要
└── 2026-11-02/
    ├── fia-decisions/
    │   ├── 2026-mexico-city-grand-prix---race-scrutineering.pdf
    │   └── 2026-mexico-city-grand-prix---race-scrutineering.md   ← 元信息 + 抽取的正文
    ├── fia-news/
    ├── f1-latest/
    ├── the-race/
    └── motorsport/
```

每个 `.md` 的头部是元信息（来源、链接、采集时间、本地文件路径），
分隔线下面是 PDF 抽取出来的正文。

---

## 怎么用这些素材写稿

抓下来只是第一步。真正的工作流是：

1. 打开 `archive/latest.md`，扫一眼这轮新增了什么。
2. 挑一个**有 PDF 原文**的 FIA 文件（决策、传唤、罚单）。
3. 把那个 `.md`（或 PDF）丢给 AI，用这条提示词：

```
你是 F1 规则编辑。这是 FIA 的一份原始文件。
1. 用 200 字说清它决定了什么。
2. 列出这份文件里「媒体大概率不会写、但很重要」的三个细节。
3. 找出这份文件与同类历史判罚可能不一致的地方。
4. 如果我要据此写一篇 800 字的解读，最值得切入的角度是什么？
不要写正文，只回答上面四点。
```

4. AI 回答完，挑一个角度自己写 150 字判断，剩下的让 AI 补。

这样出来的文章，**信息源头是 FIA 的 PDF**，不是 The Race 的转述。
搬运的指控从结构上就不成立了。

---

## 本地跑（可选）

不想用 GitHub，也可以在自己电脑跑，但需要能访问外网：

```bash
python3 collect.py --dry-run        # 只看抓到什么，不写文件
python3 collect.py --limit 5        # 正常跑，每个源最多 5 条
python3 collect.py --no-pdf         # 跳过 PDF 下载（只存链接）
```

macOS 上没有 `pdftotext` 的话，`.md` 里会显示「正文未抽取」，
但 PDF 文件本身已经存下来了，可以直接打开或拖给 AI。
装一下就能抽正文：

```bash
brew install poppler
```

---

## 常见问题

**Q：GitHub 在国内打不开怎么办？**
A：github.com 一般是能打开的，只是慢。如果实在慢，就靠 webhook 推送看摘要，
需要看全文时再用手机流量 / 换网络打开仓库页面。

**Q：motorsport 报 403？**
A：它的反爬会拦一部分请求。脚本已经带了浏览器 UA，多数情况能过；
偶尔失败不影响其他源，下一次会重试。

**Q：抓太多了，仓库会不会爆？**
A：不会。FIA 一个赛季的 PDF 大概几百份、几十 MB。
如果担心，把 `collect.py` 里的 `--limit 30` 改成 10。

**Q：能不能加更多源？**
A：可以。在 `collect.py` 顶部的 `SOURCES` 列表里加一条，
`type` 选 `rss` 或 `html`，照着现有的写就行。

**Q：这算不算自动化创作？**
A：不算。这个脚本只做「采集和归档」，不生成任何内容、不发布。
成稿仍然是人写的，AI 只在读文件这一步帮忙——这恰好是平台鼓励的
「合理使用工具辅助创作」。
