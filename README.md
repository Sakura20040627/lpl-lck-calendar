# 英雄联盟｜LPL & LCK 全赛事自动日历

只收录 **LPL、LCK 战队参与的比赛**，包含 LPL/LCK 联赛，以及 MSI、Worlds、First Stand、EWC 等国际赛事。没有中韩战队参与的国际对阵会被排除。

**日历订阅链接（GitHub Pages 发布成功后）**

https://sakura20040627.github.io/lpl-lck-calendar/lpl-lck-all-matches.ics

**操作说明**

1. 进入仓库 Settings → Pages，将 Build and deployment 的 Source 设置为 **GitHub Actions**。
2. 进入 Actions → Update LPL LCK International Calendar → Run workflow，等待绿色成功标志。
3. 在 iPhone 行事历 → 行事历 → 加入行事历 → 加入订阅行事历，粘贴上述 URL。
4. 如果以前订阅了全部赛事，请取消勾选或取消订阅旧日历，以免重复。颜色建议使用黄色 `FFD447`。

赛事自动更新：GitHub Actions 每小时尝试执行（非实时，GitHub 可能延迟）。iPhone 订阅同步有额外延迟。比赛时间会自动换算成手机所在时区，日本为 JST。

国际赛事中若仍显示待定队伍，只有身份确认后才会出现在日历。战队名单由本赛季 LPL、LCK 联赛赛程识别；国际赛事的队伍 ID、名称或缩写与联赛数据不一致时可能漏收，需修复匹配规则。数据源来自 LoL Esports 网站使用的非官方接口，并非 Riot 保证可用的公共 API。

首次 Pages 部署前请勿将预测的 URL 当成已可用网址。若 Actions 失败，查看该次运行的详细错误记录。