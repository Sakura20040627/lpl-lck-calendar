# 英雄联盟｜LPL、LCK 与 G2 全赛事自动日历（不含 AL）

## 筛选规则

- 保留 **LPL**、**LCK** 所有队伍的联赛对阵及国际赛事，**但完全排除 AL（Anyone's Legend）**；即使 AL 的对手是 LPL/LCK/G2 战队也不收录。
- 额外保留 **G2 Esports** 在 **LEC**、MSI、全球总决赛、First Stand、EWC 等比赛的全部已确定对阵。
- 不收录其他 LEC 战队之间、或无任何目标队伍参与的国际对阵。
- 尚未公布参赛队伍（TBD vs TBD）的国际赛不会预先添加；主办方公布对阵后会自动出现。

## iPhone 订阅网址

https://sakura20040627.github.io/lpl-lck-calendar/lpl-lck-all-matches.ics

**原有网址保持不变。** 已成功订阅的 iPhone 用户不必再次加入，Apple 重新抓取订阅文件后就会同步变化。日历颜色可用黄色 `FFD447`。

## 日历显示格式

沿用原项目 [hh-io/lol-esports-calendar](https://github.com/hh-io/lol-esports-calendar) 的 `intl.ics` 呈现习惯：

- 比赛开始前：`Worlds: GEN vs IG (瑞士轮)`
- 比赛结束后：`Worlds: GEN 1-0 IG (瑞士轮)`（示例比分，非实际赛果）
- 内容：`赛区: Worlds`、`阶段: 瑞士轮`、`赛制: BO1`、`对阵: Gen.G Esports vs Invictus Gaming`
- 时间使用 UTC 编码，iPhone 会以日本等手机设定时区自动显示本地时间。
- 保持旧日历事件 UID，避免订阅更新产生重复条目。

## 自动更新

GitHub Actions 每小时 **尝试**从 LoL Esports 非官方公开接口更新；调度可能延迟，Apple 订阅端也可能存在缓存刷新延迟。运行失败时旧文件保留。通过 [Actions 页面](https://github.com/Sakura20040627/lpl-lck-calendar/actions) 查看更新是否成功。

数据依赖 LoL Esports 比赛公开资料；队伍更名或接口发生变更时，可能暂时漏掉部分场次。非 Riot 官方项目。
