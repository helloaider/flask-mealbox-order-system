# 系统架构设计

## 整体架构

本系统采用**前后端分离**架构，后端提供 REST API，前端为纯静态单页应用（SPA），通过 HTTP 请求与后端交互。

```
┌─────────────────────────────────────────────────────┐
│                      客户端                          │
│  ┌──────────────────┐    ┌────────────────────────┐  │
│  │   用户点餐端      │    │     管理员后台          │  │
│  │  frontend/       │    │     admin/             │  │
│  │  index.html      │    │     index.html         │  │
│  └────────┬─────────┘    └───────────┬────────────┘  │
└───────────┼──────────────────────────┼───────────────┘
            │  HTTP / JSON REST API    │
            ▼                          ▼
┌─────────────────────────────────────────────────────┐
│                Flask 后端（端口 5001）               │
│                                                     │
│  ┌──────────┐ ┌──────────┐ ┌───────────┐ ┌───────┐  │
│  │/api/auth │ │/api/menu │ │/api/orders│ │/api/  │  │
│  │          │ │(公开)    │ │(用户Token)│ │admin  │  │
│  └──────────┘ └──────────┘ └───────────┘ └───┬───┘  │
│                                               │      │
│                               ┌───────────────┴───┐  │
│                               │ /api/admin/stats  │  │
│                               └───────────────────┘  │
│  ┌─────────────────────────────────────────────┐    │
│  │     SQLAlchemy ORM（joinedload 消除 N+1）    │    │
│  └──────────────────────┬──────────────────────┘    │
└─────────────────────────┼───────────────────────────┘
                          ▼
              ┌───────────────────────┐
              │   SQLite 数据库        │
              │   food_order.db       │
              │  （9张表 + 多列索引）  │
              └───────────────────────┘
```

---

## 技术选型

| 层次 | 技术 | 版本 | 说明 |
|------|------|------|------|
| 后端框架 | Flask | 3.0.3 | 轻量 Python Web 框架 |
| ORM | Flask-SQLAlchemy | 3.1.1 | 数据库抽象层 |
| 底层 ORM | SQLAlchemy | 2.0.36 | — |
| 数据库 | SQLite | — | 文件型数据库，无需单独部署 |
| 认证 | PyJWT | 2.8.0 | JWT HS256 Token 鉴权 |
| 跨域 | Flask-CORS | 4.0.1 | 全局开启，支持前端直接 `file://` 打开 |
| 密码加密 | Werkzeug | 3.0.3 | pbkdf2:sha256 哈希存储 |
| 前端 | 原生 HTML/CSS/JS | — | 无框架，单文件，零构建 |
| 前端图表 | Chart.js | 4.4.0（CDN）| 管理端统计图表 |

---

## 目录结构

```
order_dishes/
├── backend/                  # 后端全部代码
│   ├── app.py                # 应用入口：蓝图注册、DB 初始化、自动补列、静态托管
│   ├── models.py             # ORM 数据模型（9张表，含索引定义）
│   ├── config.py             # 配置（JWT 密钥，支持环境变量）
│   ├── utils.py              # JWT 鉴权装饰器（student_required / admin_required）
│   ├── seed.py               # 初始数据（管理员 + 菜品 + 12种套餐 + 米饭）
│   ├── food_order.db         # SQLite 数据库文件（运行时生成，已加入 .gitignore）
│   ├── requirements.txt      # Python 依赖
│   └── routes/               # 路由蓝图（按业务拆分）
│       ├── __init__.py
│       ├── auth.py           # 注册 / 登录 / 个人信息（/api/auth）
│       ├── menu.py           # 菜单、套餐、取餐点、餐次、收款码、联系方式（/api/menu，公开）
│       ├── orders.py         # 用户下单 / 查询（/api/orders，需用户Token）
│       ├── admin.py          # 管理员全部接口（/api/admin，需管理员Token）
│       └── stats.py          # 统计分析（/api/admin/stats，需管理员Token）
├── frontend/
│   └── index.html            # 用户端（单文件 SPA，CSS + JS 内嵌）
├── admin/
│   └── index.html            # 管理端（单文件 SPA，CSS + JS 内嵌）
├── docs/                     # 设计文档（本目录）
├── start.bat                 # Windows 一键启动脚本
└── README.md
```

---

## 蓝图路由划分

| 蓝图 | URL 前缀 | 鉴权 | 说明 |
|------|---------|------|------|
| `auth_bp` | `/api/auth` | 公开（部分接口需 Token）| 注册、登录、个人信息 |
| `menu_bp` | `/api/menu` | 全部公开 | 菜单、套餐、取餐点、餐次状态、收款码、联系方式 |
| `orders_bp` | `/api/orders` | 需用户 Token | 下单、查我的订单 |
| `admin_bp` | `/api/admin` | 需管理员 Token（除 login）| 订单管理、菜品/套餐/取餐点/餐次/收款码/用户管理 |
| `stats_bp` | `/api/admin/stats` | 需管理员 Token | 统计分析 |

---

## 部署模式

### 本地 / 局域网部署（当前）

```
浏览器
    │
    ├─ GET http://localhost:5001/           → Flask 托管 frontend/index.html
    ├─ GET http://localhost:5001/admin      → Flask 托管 admin/index.html
    └─ POST/GET http://localhost:5001/api/… → REST API
```

Flask 同时承担静态文件服务和 API 服务，通过 `send_from_directory` 托管两个前端页面。  
前端也可以直接用浏览器打开本地 HTML 文件（`file://` 协议），CORS 已全局开启。

启动后自动打印本机局域网 IP，手机与电脑连同一 WiFi 即可扫码访问。

### 启动命令

```bash
cd backend
pip install -r requirements.txt
python app.py
```

或双击根目录 `start.bat`（Windows 一键启动）。

---

## 关键设计决策

### 1. 单文件前端

每个页面只有一个 HTML 文件，CSS、JS 内嵌其中。  
优点：无需构建工具，部署简单，可直接双击打开。  
代价：文件体积大，无模块边界，功能多后维护成本上升。  
适用边界：功能模块 ≤ 5 个、代码量 ≤ 500 行时优先考虑；超出后建议拆分文件。

### 2. SQLite 作为数据库

适合小规模场景（并发低、数据量小）。`food_order.db` 文件随项目携带，无需安装数据库服务。  
如需扩展，只需修改 `SQLALCHEMY_DATABASE_URI` 切换到 PostgreSQL / MySQL，ORM 层无需改动。

### 3. JWT 无状态认证

Token 存储在浏览器 `localStorage`，每次请求通过 `Authorization: Bearer <token>` 携带。  
用户 Token 有效期 30 天，管理员 Token 有效期 7 天。  
密钥通过环境变量 `FOOD_SECRET_KEY` 配置，有默认值兜底（生产环境务必修改）。

### 4. joinedload 消除 N+1

`Order`、`OrderItem` 关联关系均使用 `lazy='joined'`，配合路由层的 `options(joinedload(...))` 确保深层关联也被预加载，N 单数据只需 1 次 SQL 查询。

```python
# 消除 N+1 示例
Order.query.options(
    joinedload(Order.items).joinedload(OrderItem.menu_item),
    joinedload(Order.session),
    joinedload(Order.pickup_point),
).all()
```

### 5. 数据库索引

`models.py` 中为高频查询字段定义索引：

```python
# orders 表
ix_orders_user_id      # 按用户查历史订单
ix_orders_session_id   # 按餐次筛选
ix_orders_status       # 按状态筛选
ix_orders_created_at   # 按时间排序

# order_items 表
ix_order_items_order_id      # 查订单明细
ix_order_items_menu_item_id  # 统计菜品销量
```

### 6. 自动数据库迁移（补列）

`app.py` 启动时用 SQLAlchemy `inspect` 检测表是否缺列，缺失则自动 `ALTER TABLE` 补列：

| 列 | 迁移说明 |
|----|---------|
| `orders.session_id` | 关联餐次功能上线时新增 |
| `orders.pickup_point_id` | 取餐点功能上线时新增 |
| `orders.payment_note` | 转账备注功能上线时新增 |
| `combo_types.is_featured` | 套餐推荐功能上线时新增 |
| `users.class_name` | 用户备注功能上线时新增 |

`system_config` 表由 `db.create_all()` 自动创建（新表，无需 ALTER）。

### 7. 餐次机制（点餐开关）

用 `OrderSession` 表承载时间维度的下单控制（`order_start ~ order_end`），与 `PickupPoint` 的空间概念完全解耦。  
前端每 60 秒静默轮询 `/api/menu/session`，自动切换点餐开关，无需刷新页面。

### 8. 统计模块内存聚合

`stats.py` 全量加载订单后在 Python 内存中聚合（按日期、状态、菜品等分组），适合数据量小的场景。  
内部使用 IN 查询 + 字典缓存替代循环内单条查询，消除 N+1：

```python
mi_ids = list({item.menu_item_id for item in items})
mi_map = {m.id: m for m in MenuItem.query.filter(MenuItem.id.in_(mi_ids)).all()}
```

### 9. 非阻塞前端加载

用户端登录后立即展示页面框架，菜单数据在后台异步加载（不 `await`），加载期间显示骨架占位动画，不阻塞界面交互。

```javascript
async function showMain() {
  document.getElementById('main-page').style.display = 'block';
  // 显示骨架占位，异步加载，不阻塞
  loadMenu();  // 不 await
}
```

### 10. 全局 Loading 计数器

所有用户触发的 HTTP 请求均通过 `fetchWithLoading(url, opts)` 包装，内部维护计数器：

```javascript
let _loadingCount = 0;
function showLoading() { _loadingCount++; ... }
function hideLoading() { _loadingCount = Math.max(0, _loadingCount - 1); ... }
```

支持并发请求叠加，任意一个请求在途时右上角小菊花持续旋转，全部完成后消失。  
后台静默轮询（60 秒餐次检查）不触发 loading 菊花。
