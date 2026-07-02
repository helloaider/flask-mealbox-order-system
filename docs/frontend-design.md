# 前端设计文档

## 概述

前端分为两个独立页面，均为**单文件 SPA**（CSS + JS 全部内嵌于 HTML），无需构建工具，可直接用浏览器打开，也可由 Flask 托管访问。

| 页面 | 文件 | 用户 | 访问方式 |
|------|------|------|---------|
| 用户点餐端 | `frontend/index.html` | 点餐用户 | http://localhost:5001/ |
| 管理后台 | `admin/index.html` | 餐厅管理员 | http://localhost:5001/admin |

---

## 全局 Loading 小菊花

两个页面均实现了统一的 HTTP 请求指示器：右上角固定位置的旋转小圆圈，无遮罩、不阻断操作。

```css
#g-loading {
  position: fixed;
  top: 14px; right: 14px;
  z-index: 9999;
  pointer-events: none;   /* 不拦截点击穿透 */
}
.g-spin {
  width: 22px; height: 22px;
  border: 2.5px solid rgba(255,107,53,.25);
  border-top-color: var(--primary);
  border-radius: 50%;
  animation: g-spin-anim .65s linear infinite;
}
```

**JS 计数器控制（支持并发请求叠加）：**

```javascript
let _loadingCount = 0;

function showLoading() {
  _loadingCount++;
  document.getElementById('g-loading').style.display = 'block';
}
function hideLoading() {
  _loadingCount = Math.max(0, _loadingCount - 1);
  if (_loadingCount === 0)
    document.getElementById('g-loading').style.display = 'none';
}
async function fetchWithLoading(url, opts) {
  showLoading();
  try { return await fetch(url, opts); }
  finally { hideLoading(); }
}
```

所有用户触发的 HTTP 请求（登录、提交订单、切换状态等）均通过 `fetchWithLoading` 包装。  
后台静默轮询（60 秒餐次检查）**不触发**菊花，直接 `fetch` 调用。

---

## 用户点餐端（`frontend/index.html`）

### 页面结构

```
┌──────────────────────────────────┐
│           登录/注册页             │  ← 未登录时显示（深色背景 + 浮动装饰粒子）
└──────────────────────────────────┘
            ↓ 登录成功
┌──────────────────────────────────┐
│  顶部栏                          │
│  左：🍱 + 用户姓名·手机尾号       │
│  右：[👤 资料] [📞 联系] [退出]   │
├──────────────────────────────────┤
│  Tab 导航：[🍽️ 点餐] [📋 我的订单]│
├──────────────────────────────────┤
│                                  │
│   ── 点餐 Tab ──                 │
│   ┌──────────────────────────┐   │
│   │ 餐次横幅（名称/时间/送餐）│   │
│   │ 取餐点列表卡片           │   │
│   ├──────────────────────────┤   │
│   │ ⚡ 快选套餐              │   │
│   │  推荐套餐卡片（默认展示）│   │
│   │  ▼ 查看更多套餐（N个）  │   │
│   │  折叠套餐（点击展开）   │   │
│   ├──────────────────────────┤   │
│   │ 🥘 自由选菜              │   │
│   │  荤菜 / 素菜两栏列表    │   │
│   └──────────────────────────┘   │
│                                  │
│   ── 我的订单 Tab ──             │
│   ┌──────────────────────────┐   │
│   │ 搜索框（本地过滤）       │   │
│   │ 订单卡片列表             │   │
│   └──────────────────────────┘   │
│                                  │
├──────────────────────────────────┤
│  底部购物车栏（固定，点餐开放时）  │
│  [🛒 N] [已选 ¥XX] [去结算 →]    │
└──────────────────────────────────┘
              ↕ 上划
┌──────────────────────────────────┐
│  购物车抽屉（底部弹出）           │
│  商品列表（套餐 or 自选明细）      │
│  ── 下单配置 ──                  │
│  餐次选择（多餐次时展示）          │
│  取餐点下拉卡片                   │
│  备注输入框                       │
│  ── 支付 ──                      │
│  收款码（微信/支付宝切换）        │
│  应付金额                         │
│  转账备注输入框                   │
│  [💳 已付款，提交订单]            │
└──────────────────────────────────┘
```

### 登录/注册页

- 深色背景（`#1a0a00`）+ 橙色径向光晕 + 浮动食物装饰粒子（`@keyframes floatDeco`）
- 玻璃拟态卡片（`backdrop-filter: blur(24px)`）
- Tab 切换：登录 / 注册，切换时清空密码字段
- 注册时密码字段不 `strip`，保留原始输入
- 登录页支持"记住密码"勾选框（明文存 `localStorage.saved_login`）
- 登录/注册按钮在请求期间设为 `disabled` 防重复点击

### 非阻塞启动

```javascript
async function showMain() {
  // 立即展示主界面框架，不等待数据
  document.getElementById('main-page').style.display = 'block';
  // 骨架占位动画
  document.getElementById('order-body').innerHTML = '/* 骨架 HTML */';
  loadMenu();   // 不 await，后台加载
}
```

`loadMenu()` 并行发出菜单/套餐/取餐点/餐次等请求，加载完成后渲染完整点餐界面；加载失败显示错误提示，不崩溃。

### 全局状态变量

```javascript
let token        // JWT Token（登录后设置）
let currentUser  // {id, name, phone, class_name}
let menuItems    // 全部可用菜品数组
let combos       // 套餐类型数组（含 is_featured）
let pickupPoints // 启用的取餐点数组
let openSessions // 当前开放 + upcoming 餐次数组
let cart         // 自选购物车：{menu_item_id: quantity}
let selCombo     // 当前选中的套餐对象，null = 未选
let cachedOrders // 我的订单缓存（用于本地搜索过滤）
```

### 套餐推荐折叠

```
is_featured=True  → 推荐区，默认可见，右上角"★ 推荐"橙色标签
is_featured=False → 折叠区，隐藏在"▼ 查看更多套餐（N个）"按钮后

全部 is_featured=False → 全量展示，无折叠按钮（兼容旧数据）
```

折叠区用 `max-height` CSS 过渡动画（平滑展开/收起）。

### 餐次控制

- 每 60 秒静默轮询 `GET /api/menu/session`（`setInterval`，直接 `fetch`，不显示菊花）
- `is_open=false` → 隐藏点餐区和购物车栏，显示"当前不在点餐时间"
- `is_open=true` → 正常展示点餐界面
- 退出登录时清除 `sessionCheckTimer`，防内存泄漏

### 我的订单本地搜索

"我的订单"列表一次性加载到 `cachedOrders`，搜索框输入时在前端过滤（`filterMyOrders`），带 200ms debounce，不发网络请求，响应即时。

### 订单状态展示

| 状态 | 中文 | 颜色 | 说明 |
|------|------|------|------|
| unpaid | 待收款 | 橙色 | 用户已提交，等管理员确认 |
| pending | 待制作 | 灰色 | 已收款，等厨房接单 |
| preparing | 制作中 | 黄色 | 厨房正在制作 |
| delivering | 配送中 | 蓝色 | 正在配送 |
| delivered | 已送达 | 绿色 | 终态 |

### 个人资料弹窗

"👤 资料"按钮触发底部抽屉，可修改姓名、备注（class_name），可选修改密码（需输入旧密码）。调用 `PUT /api/auth/me`，成功后更新 `localStorage.user` 和顶部栏显示。

---

## 管理后台（`admin/index.html`）

### 页面结构

```
┌──────────┬─────────────────────────────────────────┐
│  侧边栏  │           顶部栏（手机端显示汉堡菜单）    │
│  220px   ├─────────────────────────────────────────┤
│          │                                         │
│ 📋 订单  │          主内容区                        │
│ 🥘 菜品  │     各面板通过 CSS display 切换          │
│ 🍱 套餐  │          （不重新加载 DOM）               │
│ 🗓️ 餐次  │                                         │
│ 📍 取餐点│                                         │
│ 💳 收款码│                                         │
│ 📊 统计  │                                         │
│ 👥 用户  │                                         │
│ ⚙️ 设置  │                                         │
└──────────┴─────────────────────────────────────────┘
```

### 订单管理面板

**筛选层（从上到下依次作用）：**

1. 搜索框：订单号（精确）/ 姓名 / 手机号 / 地址 / 备注（模糊，后端 `ILIKE`）
2. 餐次下拉：自定义样式（胶囊形触发器 + 浮层菜单，内含状态颜色点 + 餐次名 + 时间段 + 状态标签）
3. 状态 Tab：全部 / 待收款 / 待制作 / 制作中 / 配送中 / 已送达

**自动刷新**：停留在订单面板时每 30 秒调用 `loadOrders(currentStatus)`；切换到其他面板时暂停定时器，切回恢复，避免不必要的请求。

**操作按钮（由当前订单状态决定）：**

| 当前状态 | 按钮 | 下一状态 |
|---------|------|---------|
| unpaid | 💰 确认收款 | pending |
| pending | ✅ 接单制作 | preparing |
| preparing | 🛵 开始配送 | delivering |
| delivering | ✔️ 确认送达 | delivered |

**批量操作**：勾选订单卡片后底部出现浮动批量栏，按钮根据当前筛选状态智能显示，`Promise.all` 并行请求，统一 loading。

**餐次筛选下拉样式（`.custom-select`）：**

```
胶囊形触发按钮（border-radius: 20px，边框 + 文字）
    ↓ 点击
浮层菜单（绝对定位，带入场动画 slideDown，点击外部自动关闭）
    每个选项：
        状态颜色圆点  +  餐次名称  +  时间段  +  状态标签（pill）
```

内部用隐藏 `<input type="hidden" id="session-filter">` 存储选中值，供其他逻辑读取。

### 菜品管理面板

- 列表展示所有菜品（含下架），上架/下架状态用颜色区分
- 支持新增（name + category + emoji）、编辑（行内编辑 / 弹窗）、软删除（下架）
- emoji 输入框 + 常用 emoji 快选按钮

### 套餐管理面板

- 按 meat_count / veg_count 排序展示
- 新增/编辑套餐时，输入荤素数量后自动调用 `GET /api/admin/combos/calc-price` 填入建议价格
- 推荐状态切换按钮，点击后卡片实时更新"★ 推荐"标签

### 餐次管理面板

- 列表含实时状态标签（`upcoming` 蓝色 / `open` 绿色 / `ended` 灰色 / `closed` 红色）
- 新增时时间格式提示：`YYYY-MM-DD HH:MM`

### 取餐点管理面板

- 启用/禁用开关控制是否在用户端展示（独立于点餐时间控制）
- 编辑字段：名称、地点、开放时间段描述、备注

### 收款码面板

- 上传图片后前端转 Base64，`PUT /api/admin/qrcode/<type>` 存入数据库
- 也支持填写收款链接（URL 形式）
- 上传预览：页面内实时展示已保存的收款码

### 统计面板

**筛选控件：**
- 时间范围：今天 / 本周 / 本月 / 全部（默认全部）
- 餐次筛选：同款自定义下拉

**图表（Chart.js 4.4.0，CDN 引入）：**

| 图表 | 类型 | 数据来源 |
|------|------|---------|
| 订单状态分布 | 圆环图（Doughnut）| `status_dist` |
| 收入趋势 | 折线图（Line）+ 柱状图（Bar）| `revenue_trend` |
| 热门菜品 Top10 | 横向柱状图（Bar horizontal）| `top_dishes` |
| 下单时段分布 | 柱状图（Bar）| `hourly_dist` |
| 套餐销售分布 | 圆环图 | `combo_dist` |
| 支付渠道分布 | 圆环图 | `channel_dist` |

每次切换筛选条件重新渲染时，先 `destroy()` 旧 Chart 实例，再创建新实例（防内存泄漏）。

**CSV 导出：**
- 生成 UTF-8 BOM 格式（兼容 Excel 直接打开）
- 特殊字符（逗号/引号/换行）用 `escape` 函数处理

### 用户管理面板

- 列表展示注册用户（姓名/手机/备注/注册时间/历史订单数）
- 搜索框后端模糊搜索（姓名/手机/备注）
- 删除用户同时删除其全部订单明细和订单（`DELETE /api/admin/users/<id>`）

### 商家设置面板

配置联系方式（微信号 / 电话 / 补充说明），存入 `system_config` 表，用户端"📞 联系"弹窗展示。

---

## 响应式设计

### 用户端
- `max-width: 600px` 居中布局，天然适配手机屏幕
- 点餐区套餐卡片：2~3 列 → 手机 2 列
- 自选菜品：左荤右素双栏

### 管理端

| 断点 | 变化 |
|------|------|
| > 768px | 固定侧边栏 220px，主内容区自适应 |
| ≤ 768px | 侧边栏隐藏，顶部汉堡菜单（☰），点击展开带遮罩，点击遮罩关闭 |

响应式变化细节：
- 统计汇总卡片：5列 → 3列（手机）
- 订单卡片：多列 → 单列
- 套餐卡片：3列 → 2列
- 取餐点操作按钮：横排 → 竖排

---

## 设计规范

### 色彩变量（`:root`）

```css
--primary: #FF6B35    /* 主色：橙红，按钮/高亮/loading 圆圈 */
--light:   #fff0ea    /* 主色浅版，选中态背景 */
--dark:    #2C3E50    /* 深色：标题/侧边栏背景 */
--green:   #27ae60    /* 成功/已送达 */
--yellow:  #f39c12    /* 警告/制作中 */
--blue:    #3498db    /* 信息/配送中 */
--danger:  #e74c3c    /* 危险/删除 */
```

### 圆角规范

| 元素 | 圆角 |
|------|------|
| 内容卡片 | 12px ~ 14px |
| 按钮 | 8px ~ 12px |
| 输入框 | 10px ~ 12px |
| 胶囊标签 / 筛选按钮 | 20px（border-radius: 20px）|
| 底部抽屉 / 弹窗 | 16px ~ 20px（顶部圆角）|

### 字体

- 正文：`'PingFang SC', 'Helvetica Neue', sans-serif`
- 标题/价格：font-weight 700 ~ 800
- 状态标签：font-size 12px ~ 13px

### 交互反馈

- Toast 提示（右下角滑入，3 秒自动消失）代替 `alert()`
- 成功下单弹窗：显示订单号 + 金额，可点击关闭或跳转到"我的订单"
- 表单提交期间按钮 `disabled`，防重复点击
- 搜索框 200ms debounce，避免频繁触发过滤
