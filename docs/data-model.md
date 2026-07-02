# 数据模型设计

## ER 图（实体关系）

```
┌──────────┐        ┌──────────────────────────┐        ┌────────────────┐
│  users   │        │         orders           │        │  order_items   │
├──────────┤  1:N   ├──────────────────────────┤  1:N   ├────────────────┤
│ id (PK)  │───────▶│ id (PK)                  │───────▶│ id (PK)        │
│ name     │        │ user_id (FK) [idx]        │        │ order_id [idx] │
│ phone    │        │ order_type               │        │ menu_item_id   │
│ password │        │ combo_type_id (FK, 可空) │        │   [idx]        │
│ _hash    │        │ total_price              │        │ quantity       │
│ class_   │        │ status [idx]             │        │ price          │
│ name     │        │ payment_note             │        └───────┬────────┘
│ created  │        │ payment_channel          │                │ N:1
│ _at      │        │ note                     │                ▼
└──────────┘        │ address                  │        ┌────────────────┐
                    │ session_id (FK) [idx]    │        │   menu_items   │
                    │ pickup_point_id (FK)     │        ├────────────────┤
                    │ created_at [idx]         │        │ id (PK)        │
                    └────────┬─────────────────┘        │ name           │
                             │                          │ category       │
                             │  N:1                     │ price          │
                    ┌────────┘                          │ is_available   │
                    ▼                                   │ emoji          │
             ┌──────────────┐                          └────────────────┘
             │ combo_types  │
             ├──────────────┤    ┌────────────────────┐
             │ id (PK)      │    │   order_sessions   │
             │ name         │    ├────────────────────┤
             │ meat_count   │    │ id (PK)            │
             │ veg_count    │    │ name               │
             │ price        │    │ order_start        │
             │ description  │    │ order_end          │
             │ is_featured  │    │ deliver_time       │
             └──────────────┘    │ note               │
                                 │ is_active          │
  ┌──────────┐                   │ created_at         │
  │  admins  │                   └────────────────────┘
  ├──────────┤
  │ id (PK)  │    ┌──────────────┐    ┌──────────────┐
  │ username │    │ pickup_points│    │system_config │
  │ password │    ├──────────────┤    ├──────────────┤
  │ _hash    │    │ id (PK)      │    │ id (PK)      │
  └──────────┘    │ name         │    │ key (UNIQUE) │
                  │ location     │    │ value (TEXT) │
                  │ open_time    │    │ updated_at   │
                  │ note         │    └──────────────┘
                  │ is_active    │
                  │ updated_at   │
                  └──────────────┘
```

---

## 表结构详情

### users（注册用户）

| 字段 | 类型 | 约束 | 说明 |
|------|------|------|------|
| id | INTEGER | PK, 自增 | 用户 ID |
| name | VARCHAR(50) | NOT NULL | 真实姓名 |
| phone | VARCHAR(20) | UNIQUE, NOT NULL | 手机号（登录账号）|
| password_hash | VARCHAR(256) | NOT NULL | Werkzeug pbkdf2:sha256 哈希 |
| class_name | VARCHAR(50) | DEFAULT '' | 备注信息（部门/楼栋/班级等，选填）|
| created_at | DATETIME | DEFAULT utcnow | 注册时间 |

---

### admins（管理员）

| 字段 | 类型 | 约束 | 说明 |
|------|------|------|------|
| id | INTEGER | PK, 自增 | 管理员 ID |
| username | VARCHAR(50) | UNIQUE, NOT NULL | 用户名 |
| password_hash | VARCHAR(256) | NOT NULL | bcrypt 哈希 |

默认账号：`admin` / `admin123`（`seed.py` 首次启动时写入）

---

### menu_items（菜品）

| 字段 | 类型 | 约束 | 说明 |
|------|------|------|------|
| id | INTEGER | PK, 自增 | 菜品 ID |
| name | VARCHAR(50) | NOT NULL | 菜品名称 |
| category | VARCHAR(10) | NOT NULL | 分类：`荤`、`素`、`主食` |
| price | FLOAT | NOT NULL | 单价（元）；主食米饭为 2.0，荤素菜品为 0.0（计费不使用此字段）|
| is_available | BOOLEAN | DEFAULT True | 是否上架（False = 软删除）|
| emoji | VARCHAR(10) | DEFAULT '🍽️' | 展示用 Emoji |

**预置菜品（`seed.py` 首次启动写入）：**

| 分类 | 菜品 |
|------|------|
| 荤 | 红烧肉🥩、可乐鸡翅🍗、鱼香肉丝🍖、宫保鸡丁🍗、糖醋排骨🥩、回锅肉🍖 |
| 素 | 炒青菜🥬、土豆丝🥔、番茄炒蛋🍅、豆腐脑🫘、清炒藕片🌿、木耳炒蛋🍄 |
| 主食 | 米饭🍚（每单自动附带，不可手动选择，price=2.0）|

> 管理员只能通过后台添加 `荤`/`素` 菜品，主食由 `seed.py` 管理。  
> 菜品不支持物理删除，只能软删除（`is_available=False`），确保历史订单关联完整性。

---

### combo_types（套餐类型）

| 字段 | 类型 | 约束 | 说明 |
|------|------|------|------|
| id | INTEGER | PK, 自增 | 套餐 ID |
| name | VARCHAR(50) | NOT NULL | 套餐名称 |
| meat_count | INTEGER | NOT NULL | 荤菜数量 |
| veg_count | INTEGER | NOT NULL | 素菜数量 |
| price | FLOAT | NOT NULL | 套餐价格（固定，计费使用此字段）|
| description | VARCHAR(200) | DEFAULT '' | 套餐描述 |
| is_featured | BOOLEAN | DEFAULT False | 是否为推荐套餐（用户端默认展示）|

**预置套餐（共 12 种，`seed.py` 写入，每次启动自动同步价格）：**

定价公式：`price = 10 + 荤数×2 + 素数×1`（底座 8 元 + 米饭 2 元）

| 套餐名 | 荤数 | 素数 | 价格 |
|--------|------|------|------|
| 一素套餐 | 0 | 1 | ¥11 |
| 两素套餐 | 0 | 2 | ¥12 |
| 三素套餐 | 0 | 3 | ¥13 |
| 一荤一素套餐 | 1 | 1 | ¥13 |
| 一荤两素套餐 | 1 | 2 | ¥14 |
| 一荤三素套餐 | 1 | 3 | ¥15 |
| 两荤一素套餐 | 2 | 1 | ¥15 |
| 两荤两素套餐 | 2 | 2 | ¥16 |
| 两荤三素套餐 | 2 | 3 | ¥17 |
| 三荤一素套餐 | 3 | 1 | ¥17 |
| 三荤两素套餐 | 3 | 2 | ¥18 |
| 三荤三素套餐 | 3 | 3 | ¥19 |

---

### order_sessions（点餐餐次）

| 字段 | 类型 | 约束 | 说明 |
|------|------|------|------|
| id | INTEGER | PK, 自增 | 餐次 ID |
| name | VARCHAR(100) | NOT NULL | 餐次名称（如"7月2日 中午场"）|
| order_start | DATETIME | NOT NULL | 开始下单时间（本地时间存储）|
| order_end | DATETIME | NOT NULL | 截止下单时间（本地时间存储）|
| deliver_time | VARCHAR(50) | DEFAULT '' | 预计送餐时间描述（纯文本，如"12:00"）|
| note | VARCHAR(200) | DEFAULT '' | 餐次备注 |
| is_active | BOOLEAN | DEFAULT True | 是否启用（False 时状态为 `closed`）|
| created_at | DATETIME | DEFAULT utcnow | 创建时间 |

**餐次状态（服务端使用本地时间 `datetime.now()` 实时计算）：**

| status | 条件 |
|--------|------|
| `upcoming` | `is_active=True` 且 `now < order_start` |
| `open` | `is_active=True` 且 `order_start ≤ now ≤ order_end` |
| `ended` | `is_active=True` 且 `now > order_end` |
| `closed` | `is_active=False` |

> 时间存储使用本地时间（非 UTC），与管理员输入保持一致，避免 8 小时时区偏差问题。

---

### pickup_points（取餐点）

| 字段 | 类型 | 约束 | 说明 |
|------|------|------|------|
| id | INTEGER | PK, 自增 | 取餐点 ID |
| name | VARCHAR(100) | NOT NULL | 取餐点名称 |
| location | VARCHAR(200) | NOT NULL | 详细地点描述 |
| open_time | VARCHAR(100) | DEFAULT '' | 取餐时间段（如"11:30-12:30"）|
| note | VARCHAR(200) | DEFAULT '' | 备注说明 |
| is_active | BOOLEAN | DEFAULT True | 是否启用（控制是否在用户端展示）|
| updated_at | DATETIME | onupdate 自动更新 | 最后修改时间 |

> `is_active` 只控制用户端展示，与点餐开关（`OrderSession`）完全解耦。

---

### orders（订单）

| 字段 | 类型 | 约束 | 索引 | 说明 |
|------|------|------|------|------|
| id | INTEGER | PK, 自增 | — | 订单 ID |
| user_id | INTEGER | FK → users.id | `ix_orders_user_id` | 下单用户 |
| session_id | INTEGER | FK → order_sessions.id, 可空 | `ix_orders_session_id` | 所属餐次 |
| pickup_point_id | INTEGER | FK → pickup_points.id, 可空 | — | 所选取餐点 |
| order_type | VARCHAR(10) | NOT NULL | — | `combo` 或 `custom` |
| combo_type_id | INTEGER | FK → combo_types.id, 可空 | — | 套餐类型（combo 时非空）|
| total_price | FLOAT | NOT NULL | — | 实付金额 |
| status | VARCHAR(20) | DEFAULT 'unpaid' | `ix_orders_status` | 订单状态 |
| payment_note | VARCHAR(100) | DEFAULT '' | — | 转账备注（手机号后四位）|
| payment_channel | VARCHAR(20) | DEFAULT 'wechat' | — | 支付渠道：`wechat`/`alipay`/`cash` |
| note | VARCHAR(200) | DEFAULT '' | — | 用户备注 |
| address | VARCHAR(100) | DEFAULT '' | — | 取餐地址文本快照（下单时固定）|
| created_at | DATETIME | DEFAULT utcnow | `ix_orders_created_at` | 下单时间 |

**订单状态流转（单向，后端状态机校验，允许跳级但禁止回退）：**

```
unpaid（待收款）
    │  管理员调用 confirm_payment 接口
    ▼
pending（待制作）
    │  管理员更新状态
    ▼
preparing（制作中）
    │  管理员更新状态
    ▼
delivering（配送中）
    │  管理员更新状态
    ▼
delivered（已送达，终态）
```

---

### order_items（订单明细）

| 字段 | 类型 | 约束 | 索引 | 说明 |
|------|------|------|------|------|
| id | INTEGER | PK, 自增 | — | 明细 ID |
| order_id | INTEGER | FK → orders.id | `ix_order_items_order_id` | 所属订单 |
| menu_item_id | INTEGER | FK → menu_items.id | `ix_order_items_menu_item_id` | 菜品 |
| quantity | INTEGER | DEFAULT 1 | — | 数量 |
| price | FLOAT | NOT NULL | — | 下单时价格快照 |

> **价格快照**：`price` 在下单时从 `MenuItem.price` 复制（套餐菜品各自记录原单价；自选菜品统一为 `0.0`，实际金额看 `Order.total_price`）。历史订单金额不随菜品改价而变化。

> 菜品被软删除后，`OrderItem.to_dict()` 中 name 显示"已删除"，不影响历史记录展示。

---

### system_config（系统配置）

| 字段 | 类型 | 约束 | 说明 |
|------|------|------|------|
| id | INTEGER | PK, 自增 | 配置 ID |
| key | VARCHAR(50) | UNIQUE, NOT NULL | 配置键名 |
| value | TEXT | NOT NULL, DEFAULT '' | 配置值（支持长文本，如 Base64 图片）|
| updated_at | DATETIME | onupdate 自动更新 | 最后修改时间 |

**已使用的配置键：**

| 键名 | 说明 |
|------|------|
| `qr_wechat` | 微信收款码（Base64 格式，`data:image/png;base64,...`）|
| `qr_alipay` | 支付宝收款码（Base64 格式）|
| `qr_wechat_url` | 微信收款链接（可选，与图片并存）|
| `qr_alipay_url` | 支付宝收款链接（可选）|
| `contact_wechat` | 商家微信号 |
| `contact_phone` | 商家联系电话 |
| `contact_remark` | 商家补充说明 |

> `SystemConfig.get(key, default)` / `SystemConfig.set(key, value)` 为静态方法，提供 key-value 存取接口。

---

## ORM 关系配置

```python
# Order 模型（lazy='joined' 消除 N+1，SELECT 时自动 JOIN）
items        = relationship('OrderItem',    lazy='joined')
session      = relationship('OrderSession', lazy='joined')
pickup_point = relationship('PickupPoint',  lazy='joined')

# OrderItem 模型（预加载关联菜品）
menu_item = relationship('MenuItem', lazy='joined')

# User 模型
orders = relationship('Order', backref='user', lazy=True)
```

路由层列表查询时额外指定 `options(joinedload(...))` 确保深层关联也被预加载：

```python
Order.query.filter_by(user_id=...).options(
    joinedload(Order.items).joinedload(OrderItem.menu_item),
    joinedload(Order.session),
    joinedload(Order.pickup_point),
).all()
# 效果：N 单数据只需 1 次 SQL JOIN 查询，消除 N+1 问题
```

---

## 业务约束汇总

| 编号 | 约束 | 实现位置 |
|------|------|---------|
| 1 | 套餐随机搭配：从 `is_available=True` 的荤/素菜中随机抽取，不足则拒单 | `routes/orders.py` |
| 2 | 餐次控制下单：当前时间在 `[order_start, order_end]` 内且 `is_active=True` 才允许；也允许预约 `upcoming` 餐次 | `routes/orders.py` |
| 3 | 防重复下单：同用户同餐次有非 `delivered` 订单时，拒绝新订单 | `routes/orders.py` |
| 4 | 取餐点选择：下单写入外键 ID 和地址文本快照，两者共存 | `routes/orders.py` |
| 5 | 菜品软删除：下架只改 `is_available=False`，保留历史关联 | `routes/admin.py` |
| 6 | 价格快照：`OrderItem.price` 在下单时固定，与菜品改价解耦 | `routes/orders.py` |
| 7 | 米饭自动附带：下单时后端自动追加米饭 `OrderItem`，套餐和自选均适用 | `routes/orders.py` |
| 8 | 套餐推荐折叠：`is_featured=True` 的套餐在用户端默认展示，其余折叠 | 前端逻辑 |
| 9 | 状态机：订单状态只允许向前流转，后端校验，禁止逆向切换 | `routes/admin.py` |
| 10 | 自动补列：`app.py` 启动时检测缺失字段并 `ALTER TABLE` 补全，兼容旧数据库 | `app.py` |
