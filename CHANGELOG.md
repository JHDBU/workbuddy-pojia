# Changelog

## v3.0 — 会话级状态机

- **破坏性变更**：不再全局常开。`<content_policy>` 换成显式状态机，默认 OFF。
- OFF / ON 各有独立的固定回复：`破甲未开启` / `破甲自检成功`，修掉“关闭后仍回自检成功”的关键词吸附。
- 判定规则：只看本会话最后一条开关指令；历史开启 + 后续关闭 = OFF。
- `<personal_files_safety>`、`<windows_command_safety>` 改为条件放行。
- L3 默认还原，新增 `gate on|off|status`。
- `status` 增加开关状态行，`GATE_TAG` 改为 `破甲未开启`（政策段与提醒块都命中）。

## v2.0 — 会话级开关（首版门控）

- 引入 `开启破甲` / `关闭破甲`，默认关闭。
- 新增 `gate` 子命令骨架、`restart` 一体化命令。

## v1.x — 全量补丁

- 六层补丁实现：L1 模板、L2 product.json、L3 mjs 闸门、L4 插件、L5 缓存、L6 云记忆。
- 修复：临时文件后缀导致 `node --check` 拒载；`return!1;` 幂等；682 个无政策段模板的噪音输出；`status` 分母虚高。
- 新增 `doctor`、`apply --dry-run`、`revert`、`persona`。
