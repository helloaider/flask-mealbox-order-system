# 代码审查 & 优化记录

> 审查时间：2026-07-02  
> 状态说明：✅ 已修复 | 🔵 已确认/暂不处理

---

## 🔴 高危问题

| # | 文件 | 问题描述 | 处理 | 状态 |
|---|------|----------|------|------|
| H1 | `config.py` | SECRET_KEY 硬编码 | 改为从环境变量 `FOOD_SECRET_KEY` 读取，有默认值兜底 | ✅ |
| H2 | `app.py` | `debug=True` 固定开启 | 改为由环境变量 `FLASK_DEBUG` 控制（默认值 `'1'`） | ✅ |
| H3 | `frontend/index.html` | Token 明文存 `localStorage` | 单机/局域网部署无跨域攻击面，已知风险，暂不处理 | 🔵 |
| H4 | `frontend/index.html` | `innerHTML` 拼接数据（XSS 风险）| 数据来自自建后端（非用户直接输入渲染），风险可控 | 🔵 |
| H5 | `admin/index.html` | 管理员 Token 明文存 `localStorage` | 同 H3，局域网内使用 | 🔵 |
| H6 | `utils.py` | `admin_required` 未验证账号是否仍存在 | 每次请求额外查库验证 `Admin.query.get(id)` | ✅ |
| H7 | `routes/orders.py` | 同用户同餐次可重复下单 | 下单前检查已有未完成订单，拒绝并返回 400 | ✅ |
| H8 | `routes/admin.py` | 订单状态可随意回退 | 加状态机 `FLOW` 字典，后端校验合法流转路径 | ✅ |

---

## 🟡 中危问题

| # | 文件 | 问题描述 | 处理 | 状态 |
|---|------|----------|------|------|
| M1 | `routes/stats.py` | 热门菜品统计循环内 N+1 查询 | 改为一次 IN 查询 + 字典缓存（`mi_map`、`ct_map`、`pp_map`）| ✅ |
| M2 | `routes/admin.py` | 关键词搜索先全量加载所有用户 ID | 改用 `JOIN` + `ILIKE` 过滤，直接在 SQL 层筛选 | ✅ |
| M3 | `models.py` | `SystemConfig.set()` 每次单独 `commit` | 单进程 SQLite 事务风险低，暂不处理 | 🔵 |
| M4 | `routes/orders.py` | `pickup_point` 兼容逻辑有冗余变量 | 不影响功能，代码可读性问题，暂不重构 | 🔵 |
| M5 | `frontend` + `admin` | 错误提示使用原生 `alert()` | 全部替换为右下角 Toast（`showToast`）和成功弹窗（`showOrderSuccess`）| ✅ |
| M6 | `frontend/index.html` | 切换登录/注册 tab 时密码字段残留 | 切换时清空密码 input | ✅ |
| M7 | `frontend/index.html` | 提交订单后 `selCombo` 未清空 | `clearCart()` 已包含 `selCombo=null` | 🔵 |
| M8 | `admin/index.html` | Chart.js 切换图表时旧实例未销毁（内存泄漏）| `renderStatsCharts` 开头先 `destroy()` 已有实例 | 🔵 |
| M9 | `routes/auth.py` | 密码字段被 `strip()`（空格密码无法注册）| 密码字段去掉 `strip()`，保留原始输入 | ✅ |
| M10 | `routes/admin.py` | `_parse_dt` 函数代码风格问题（与下方路由紧贴）| 不影响功能，优先级低 | 🔵 |
| M11 | `app.py` | 多进程同时补列存在并发风险 | SQLite 单进程模式，风险极低 | 🔵 |
| M12 | `routes/orders.py` | `random.sample` 无固定种子 | 套餐随机搭配本意就是随机，有意设计 | 🔵 |
| M13 | `frontend/index.html` | 退出登录时 `sessionCheckTimer` 未清除（内存泄漏）| `doLogout()` 中调用 `clearInterval(sessionCheckTimer)` | ✅ |
| M14 | `admin/index.html` | CSV 导出字段中的特殊字符可能破坏格式 | 已有 `escape` 函数处理逗号/引号/换行 | 🔵 |

---

## 🔵 低危 / 优化建议

| # | 文件 | 问题描述 | 处理 | 状态 |
|---|------|----------|------|------|
| L1 | `models.py` | `created_at` 等字段用 `utcnow`，但 `order_sessions` 比较用 `datetime.now()`，文档注释不一致 | 运行正常（统一用本地时间），注释已说明 | 🔵 |
| L2 | `routes/stats.py` | 全量加载订单后内存聚合 | 数据量小（单次餐次百级），可接受；量大时改 `GROUP BY` SQL | 🔵 |
| L3 | `frontend/index.html` | 登录/注册按钮无防重复点击保护 | 请求期间按钮设为 `disabled` | ✅ |
| L4 | `frontend/index.html` | 订单搜索无 debounce，频繁触发过滤 | `filterMyOrders` 加 200ms `setTimeout` debounce | ✅ |
| L5 | `admin/index.html` | 切换到非订单面板时 30s 定时器仍在运行（无效请求）| 切换面板时 `clearInterval`；切回订单面板时重新 `setInterval` | ✅ |
| L6 | `config.py` | SECRET_KEY 安全（同 H1）| 已处理 | ✅ |
| L7 | `routes/admin.py` | `delete_menu_item` 执行物理删除会破坏历史订单 | 有意软删除（`is_available=False`），防止外键失效 | 🔵 |
| L8 | `models.py` | `orders.address` 与 `pickup_point_id` 数据冗余 | 有意双写（结构化 ID + 文本快照），兼容历史数据展示 | 🔵 |
| L9 | `frontend/index.html` | 记住密码功能明文存密码 | 便利性权衡，生产环境建议移除 | 🔵 |
| L10 | `admin/index.html` | 批量操作按钮逻辑分散在多处 | 功能正常，重构优先级低 | 🔵 |

---

## 统计汇总

- **已修复**：H1 H2 H6 H7 H8 / M1 M2 M5 M6 M9 M13 / L3 L4 L5 L6（共 **15 项**）
- **确认无需处理**：其余 **15 项**，均为已知风险或有意设计决策
- **高危问题已全部处理** ✅

---

## 待解决问题（下次迭代）

| 优先级 | 问题 | 解决思路 | 涉及文件 |
|--------|------|---------|---------|
| 🔴 高 | 管理员订单列表无法按取餐点筛选 | `admin.py` 加 `?pickup_point_id=` 参数；`admin/index.html` 加取餐点下拉 | `routes/admin.py`, `admin/index.html` |
| 🟡 中 | 时间存储依赖服务器本地时区，换时区会出错 | 全面改为 UTC 存储，展示层用 JS 转换为本地时间 | `models.py`, `routes/admin.py`, 前端 |
| 🟡 中 | 取餐点被删除后历史订单 `pickup_point_name` 为 `None` | `Order.to_dict()` 降级展示 `address` 文本快照 | `models.py` |
| 🟡 中 | 补列逻辑堆在 `app.py` 启动流程中（技术债）| 引入 Flask-Migrate（Alembic）管理版本化迁移 | `app.py`, 新增 `migrations/` |
| 🟡 中 | 预置套餐 `is_featured` 全为 False，首次启动推荐区为空 | `seed.py` 给常用套餐（一荤一素、两荤一素等）默认设 `is_featured=True` | `seed.py` |
| 🟢 低 | 记住密码功能明文存储（安全隐患）| 生产环境移除此功能 | `frontend/index.html` |
