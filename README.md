# 英雄联盟｜LPL 战队国际赛自动日历

## 筛选规则

- **只收录国际赛事**：全球总决赛（Worlds）、季中冠军赛（MSI）、全球先锋赛（First Stand）、电竞世界杯（EWC），以及未来新增的 Riot 官方跨赛区国际赛事。
- **只收录至少有一支 LPL 战队参加的比赛**（含 LPL 队伍之间、LPL 对阵其他赛区队伍）；没有 LPL 战队参加的国际赛不收录。
- 不收录 LPL、LCK、LEC 等任何赛区的国内联赛、季后赛或国内杯赛。
- AL（Anyone's Legend）按一般 LPL 战队同等收录，不再特别排除。
- LPL 战队名单按当赛季 LPL 联赛赛程自动判定；对阵尚未确定（TBD）时不预先添加，官方公布对阵后自动出现。
- 官方抽签已公布、但上游赛程接口尚未更新时，已核实的对阵会通过 `src/fallback_fixtures.json` 临时补入（每条附来源，且必须通过与接口赛事相同的筛选）；接口补上后自动以接口数据为准，不会重复。

## iPhone 订阅网址

https://raw.githubusercontent.com/Sakura20040627/lpl-lck-calendar/main/public/lpl-lck-all-matches.ics

**已確認可使用的原始檔訂閱網址保持不變。** 已成功订阅的 iPhone 用户不必再次加入，Apple 重新抓取订阅文件后就会同步变化。日历颜色可用黄色 `FFD447`。

## 日历显示格式

- 比赛标题只显示队伍缩写，如 `BLG vs T1`、`TES vs GEN`、`JDG vs G2`。
- 已结束比赛仍保持 `TES vs GEN` 的标题格式，实际比分在详情的「比分」字段显示。
- 详情保留「赛区、阶段、赛制、对阵」和已结束场次的比分。
- 订阅 URL、赛事 UID 和 UTC 时区处理不变，不需要重新订阅。

## 自动更新

GitHub Actions 每小时 **尝试**从 LoL Esports 非官方公开接口更新，并将新的 ICS 内容提交到 main 分支；调度可能延迟，Apple 订阅端也可能存在缓存刷新延迟。接口故障时旧文件保留，不会清空。通过 [Actions 页面](https://github.com/Sakura20040627/lpl-lck-calendar/actions) 查看更新是否成功。

数据依赖 LoL Esports 比赛公开资料；队伍更名或接口发生变更时，可能暂时漏掉部分场次。非 Riot 官方项目。
