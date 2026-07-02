# API 接口文档

## 基础约定

- Base URL：`http://localhost:5001/api`
- 请求 / 响应格式：`application/json`
- 鉴权：需要登录的接口在 Header 中携带 `Authorization: Bearer <token>`
- 错误响应格式：`{"error": "错误信息"}`

## 鉴权说明

| Token 类型 | 获取方式 | 有效期 |
|-----------|---------|--------|
| 用户 Token | `POST /api/auth/login` 或 `/register` | 30 天 |
| 管理员 Token | `POST /api/admin/login` | 7 天 |

---

## 认证模块 `/api/auth`

### 注册

```
POST /api/auth/register
```

请求体：

```json
{
  "name": "张三",
  "phone": "13800138000",
  "password": "123456",
  "class_name": "研发部"
}
```

| 字段 | 必填 | 说明 |
|------|------|------|
| name | ✅ | 真实姓名 |
| phone | ✅ | 11 位手机号，唯一，作为登录账号 |
| password | ✅ | 密码（不 strip，保留原始输入） |
| class_name | 否 | 备注信息（部门/楼栋/班级等），选填 |

成功 201：

```json
{
  "token": "eyJ...",
  "user": { "id": 1, "name": "张三", "phone": "13800138000", "class_name": "研发部" }
}
```

错误：400（字段缺失 / 手机号格式错误 / 手机号已注册）

---

### 登录

```
POST /api/auth/login
```

请求体：

```json
{ "phone": "13800138000", "password": "123456" }
```

成功 200：返回结构同注册  
错误：401（手机号或密码错误）

---

### 获取当前用户信息

```
GET /api/auth/me
Authorization: Bearer <student_token>
```

成功 200：返回用户对象（id / name / phone / class_name）  
错误：401（未登录 / Token 已过期）

---

### 修改个人信息

```
PUT /api/auth/me
Authorization: Bearer <student_token>
```

请求体：

```json
{
  "name": "新姓名",
  "class_name": "新备注",
  "old_password": "123456",
  "new_password": "654321"
}
```

| 字段 | 必填 | 说明 |
|------|------|------|
| name | ✅ | 姓名，不得为空 |
| class_name | 否 | 备注，空字符串也接受 |
| old_password | 改密码时 | 当前密码，不改密码时省略 |
| new_password | 改密码时 | 新密码 ≥ 6 位 |

成功 200：返回更新后的用户对象  
错误：400（姓名为空 / 新密码过短 / 旧密码错误）

---

## 菜单模块 `/api/menu`（全部公开，无需登录）

### 获取菜品列表

```
GET /api/menu
```

返回所有 `is_available=true` 的菜品数组：

```json
[
  { "id": 1, "name": "红烧肉", "category": "荤", "price": 7.0, "is_available": true, "emoji": "🥩" },
  { "id": 7, "name": "炒青菜", "category": "素", "price": 3.0, "is_available": true, "emoji": "🥬" }
]
```

> 主食（米饭）也在此列表中，category 为 `主食`，前端不展示选项。

---

### 获取套餐列表

```
GET /api/menu/combos
```

返回全部套餐数组（含 `is_featured` 字段）：

```json
[
  {
    "id": 1, "name": "一荤一素套餐",
    "meat_count": 1, "veg_count": 1,
    "price": 13.0, "description": "1荤+1素+饭，经济实惠",
    "is_featured": true
  }
]
```

---

### 获取启用的取餐点

```
GET /api/menu/pickup
```

返回 `is_active=true` 的取餐点数组：

```json
[
  {
    "id": 1, "name": "1号楼门口", "location": "1号楼一楼大厅",
    "open_time": "11:30-12:30", "note": "请勿堵塞通道",
    "is_active": true, "updated_at": "2026-07-02 10:00:00"
  }
]
```

---

### 获取当前餐次状态

```
GET /api/menu/session
```

```json
{
  "is_open": true,
  "session": {
    "id": 1, "name": "7月2日 中午场",
    "order_start": "2026-07-02 10:00",
    "order_end":   "2026-07-02 11:30",
    "deliver_time": "12:00",
    "note": "",
    "is_active": true,
    "status": "open",
    "created_at": "2026-07-01 20:00:00"
  },
  "open_sessions":     [ /* 当前开放的所有餐次 */ ],
  "upcoming_sessions": [ /* 最多 3 个即将开放的餐次 */ ]
}
```

| 字段 | 说明 |
|------|------|
| `is_open` | 当前是否有开放餐次，前端据此控制点餐区是否可用 |
| `session` | 用于横幅展示：第一个开放餐次，无则取第一个 upcoming |
| `open_sessions` | 所有当前开放的餐次（可能多个，时间升序）|
| `upcoming_sessions` | 即将开放的餐次（最多 3 个，供预约选择）|

餐次 `status` 字段值：

| 值 | 含义 |
|----|------|
| `upcoming` | `is_active=True` 且当前时间 < `order_start` |
| `open` | `is_active=True` 且在 `[order_start, order_end]` 范围内 |
| `ended` | `is_active=True` 且当前时间 > `order_end` |
| `closed` | `is_active=False` |

> 前端每 60 秒静默轮询此接口（不显示 loading 菊花），自动切换点餐开关。

---

### 获取收款码

```
GET /api/menu/qrcode
```

```json
{
  "wechat":     "data:image/png;base64,...",
  "alipay":     "data:image/png;base64,...",
  "wechat_url": "https://...",
  "alipay_url": "https://..."
}
```

> 用户结算时展示，无需登录。收款码存入 `system_config` 表，Base64 格式。

---

### 获取商家联系方式

```
GET /api/menu/contact
```

```json
{
  "wechat": "wxid_xxx",
  "phone":  "13800138000",
  "remark": "营业时间 10:00-14:00"
}
```

---

## 订单模块 `/api/orders`（需用户 Token）

### 提交订单

```
POST /api/orders
Authorization: Bearer <student_token>
```

**套餐下单：**

```json
{
  "order_type":      "combo",
  "combo_type_id":   1,
  "session_id":      1,
  "pickup_point_id": 2,
  "note":            "不要辣",
  "payment_note":    "8000",
  "payment_channel": "wechat"
}
```

**自由选菜下单：**

```json
{
  "order_type":      "custom",
  "items": [
    { "menu_item_id": 1, "quantity": 1 },
    { "menu_item_id": 7, "quantity": 2 }
  ],
  "session_id":      1,
  "pickup_point_id": 2,
  "note":            "",
  "payment_note":    "8000",
  "payment_channel": "alipay"
}
```

| 字段 | 必填 | 说明 |
|------|------|------|
| `order_type` | ✅ | `combo`（套餐）或 `custom`（自由选菜）|
| `combo_type_id` | combo 时 ✅ | 套餐类型 ID |
| `items` | custom 时 ✅ | 菜品列表，至少 1 条有效菜品，主食自动过滤 |
| `session_id` | 否 | 餐次 ID；不传则自动取当前开放餐次；也可指定 upcoming 餐次（预约）|
| `pickup_point_id` | 二选一 | 取餐点 ID（`is_active=True`）|
| `address` | 二选一 | 手动填写送餐地址（兼容旧版，`pickup_point_id` 优先）|
| `note` | 否 | 用户备注 |
| `payment_note` | 否 | 转账备注（通常为手机号后四位）|
| `payment_channel` | 否 | `wechat`（默认）/ `alipay` / `cash` |

成功 201：返回完整订单对象（见下）

错误：

| 状态码 | 原因 |
|-------|------|
| 400 | 取餐点/菜品/套餐不存在、菜品不足、同餐次重复下单、餐次已结束 |
| 401 | 未登录 / Token 无效 |
| 403 | 无开放餐次且未指定餐次 |

**防重复下单**：同一用户在同一餐次已存在非 `delivered` 订单时，拒绝新订单，返回 400。

**订单对象结构：**

```json
{
  "id":               42,
  "user_id":          1,
  "user":             { "id": 1, "name": "张三", "phone": "138...", "class_name": "研发部" },
  "session_id":       1,
  "session_name":     "7月2日 中午场",
  "pickup_point_id":  2,
  "pickup_point_name":"1号楼门口",
  "order_type":       "combo",
  "combo": {
    "id": 1, "name": "一荤一素套餐",
    "meat_count": 1, "veg_count": 1,
    "price": 13.0, "description": "...", "is_featured": true
  },
  "total_price":    13.0,
  "status":         "unpaid",
  "payment_note":   "8000",
  "payment_channel":"wechat",
  "note":           "",
  "address":        "1号楼门口 - 1号楼一楼大厅",
  "created_at":     "2026-07-02 11:00:00",
  "items": [
    {
      "id": 1, "menu_item_id": 2,
      "name": "可乐鸡翅", "emoji": "🍗", "category": "荤",
      "quantity": 1, "price": 8.0
    },
    {
      "id": 2, "menu_item_id": 13,
      "name": "米饭", "emoji": "🍚", "category": "主食",
      "quantity": 1, "price": 2.0
    }
  ]
}
```

> 套餐下单时 `items` 包含后端随机抽取的荤/素菜品 + 自动附带的米饭。  
> 自由选菜下单时 `items` 包含用户所选菜品 + 米饭，`price` 均为 `0.0`（实际金额在 `total_price`）。

---

### 我的订单列表

```
GET /api/orders/my
Authorization: Bearer <student_token>
```

返回当前用户全部订单（时间倒序），使用 `joinedload` 预加载关联数据，单次查询完成。

---

## 管理员模块 `/api/admin`（需管理员 Token）

### 管理员登录

```
POST /api/admin/login
```

请求体：`{ "username": "admin", "password": "admin123" }`

成功 200：`{ "token": "...", "username": "admin" }`  
错误：401（用户名或密码错误）

---

### 订单列表

```
GET /api/admin/orders
Authorization: Bearer <admin_token>
```

查询参数：

| 参数 | 说明 |
|------|------|
| `status` | 按状态筛选：`unpaid` / `pending` / `preparing` / `delivering` / `delivered` |
| `session_id` | 按餐次 ID 筛选 |
| `q` | 关键词搜索：订单号（精确）/ 姓名 / 手机号 / 地址 / 备注（模糊）|

返回订单数组（时间倒序），使用 `joinedload` 预加载，N 单只需 1 次查询。

---

### 更新订单状态

```
PUT /api/admin/orders/<id>/status
Authorization: Bearer <admin_token>
```

请求体：`{ "status": "preparing" }`

**状态机（只允许向前流转）：**

| 当前状态 | 允许切换到 |
|---------|-----------|
| unpaid | pending |
| pending | preparing / delivering / delivered |
| preparing | delivering / delivered |
| delivering | delivered |
| delivered | （终态，不可切换）|

错误：400（状态不合法或流转被拒）

---

### 确认收款

```
POST /api/admin/orders/<id>/confirm_payment
Authorization: Bearer <admin_token>
```

无请求体，专用接口：`unpaid → pending`。  
错误：400（订单不是 unpaid 状态）

---

### 菜品管理

```
GET    /api/admin/menu              # 全部菜品（含下架，is_available=False 的也返回）
POST   /api/admin/menu              # 新增菜品
PUT    /api/admin/menu/<id>         # 编辑菜品
DELETE /api/admin/menu/<id>         # 软删除（is_available → False）
```

**新增请求体：**

```json
{ "name": "水煮鱼", "category": "荤", "emoji": "🐟" }
```

> `price` 字段保留兼容性，实际计费使用公式，不依赖菜品单价（price 统一写入 `0.0`）。  
> `category` 只允许 `荤` 或 `素`，主食菜品由 `seed.py` 写入，管理员无法通过此接口添加主食。

**编辑请求体（全部可选）：**

```json
{ "name": "新名称", "price": 0.0, "is_available": true, "emoji": "🐟" }
```

---

### 套餐管理

```
GET    /api/admin/combos                   # 列表（按 meat_count, veg_count 排序）
POST   /api/admin/combos                   # 新增
PUT    /api/admin/combos/<id>              # 编辑
DELETE /api/admin/combos/<id>              # 删除（硬删除）
POST   /api/admin/combos/<id>/featured     # 切换推荐状态（每次取反）
GET    /api/admin/combos/calc-price?meat=2&veg=1  # 计算建议价格
```

**新增请求体：**

```json
{
  "name": "两荤一素套餐",
  "meat_count": 2,
  "veg_count": 1,
  "price": 15.0,
  "description": "2荤+1素+饭"
}
```

**计算价格响应：**

```json
{ "meat": 2, "veg": 1, "price": 15.0 }
```

定价公式：`price = 10 + meat×2 + veg×1`（底座 8 元 + 米饭 2 元）

---

### 取餐点管理

```
GET    /api/admin/pickup            # 全部（含禁用的）
POST   /api/admin/pickup            # 新增
PUT    /api/admin/pickup/<id>       # 编辑（含 is_active 开关）
DELETE /api/admin/pickup/<id>       # 删除（硬删除）
```

**新增请求体：**

```json
{
  "name": "1号楼门口",
  "location": "1号楼一楼大厅",
  "open_time": "11:30-12:30",
  "note": "请勿堵塞通道"
}
```

---

### 餐次管理

```
GET    /api/admin/sessions          # 列表（时间倒序，含实时 status 字段）
POST   /api/admin/sessions          # 新增
PUT    /api/admin/sessions/<id>     # 编辑（含 is_active 开关）
DELETE /api/admin/sessions/<id>     # 删除（硬删除）
```

**新增请求体：**

```json
{
  "name": "7月2日 中午场",
  "order_start":  "2026-07-02 10:00",
  "order_end":    "2026-07-02 11:30",
  "deliver_time": "12:00",
  "note": "备注"
}
```

时间格式支持：`YYYY-MM-DD HH:MM` / `YYYY/MM/DD HH:MM` / `YYYY-MM-DDTHH:MM`（统一转为本地时间存储）

错误：400（时间格式有误 / 截止时间早于开始时间）

---

### 收款码管理

```
GET    /api/admin/qrcode                   # 获取微信+支付宝收款码和链接
PUT    /api/admin/qrcode/<type>            # 保存收款码图片（Base64）
DELETE /api/admin/qrcode/<type>            # 清除收款码
PUT    /api/admin/qrcode/<type>/url        # 保存收款链接
```

`type` 取值：`wechat` 或 `alipay`

**保存收款码请求体：**

```json
{ "image": "data:image/png;base64,..." }
```

**保存收款链接请求体：**

```json
{ "url": "https://qr.weixin.qq.com/..." }
```

---

### 商家联系方式

```
GET /api/admin/contact                     # 获取
PUT /api/admin/contact                     # 保存
```

**请求/响应体：**

```json
{ "wechat": "wxid_xxx", "phone": "13800138000", "remark": "营业时间 10:00-14:00" }
```

---

### 用户管理

```
GET    /api/admin/users             # 用户列表（时间倒序）
DELETE /api/admin/users/<id>        # 删除用户及其全部订单（硬删除）
```

**查询参数：**

| 参数 | 说明 |
|------|------|
| `q` | 关键词：姓名 / 手机号 / 备注（模糊搜索）|

**用户列表返回字段：**

```json
[
  {
    "id": 1, "name": "张三", "phone": "138...", "class_name": "研发部",
    "created_at": "2026-07-01 09:00:00", "order_count": 5
  }
]
```

---

### 统计分析

```
GET /api/admin/stats
Authorization: Bearer <admin_token>
```

查询参数：

| 参数 | 值 | 说明 |
|------|---|------|
| `range` | `today` / `week` / `month` / `all`（默认） | 时间范围 |
| `session_id` | 整数 | 筛选指定餐次（可与 range 组合）|

**响应：**

```json
{
  "summary": {
    "total_orders":     120,
    "delivered_orders": 98,
    "total_revenue":    1740.0,
    "pending_orders":   22,
    "avg_price":        14.5
  },
  "status_dist": [
    { "status": "delivered", "label": "已送达", "count": 98 }
  ],
  "revenue_trend": [
    { "label": "07/02", "revenue": 318.0, "count": 22 }
  ],
  "top_dishes": [
    { "name": "可乐鸡翅", "emoji": "🍗", "category": "荤", "count": 55 }
  ],
  "combo_dist": [
    { "name": "两荤一素套餐", "count": 42 }
  ],
  "pickup_dist": [
    { "name": "1号楼门口", "count": 60 }
  ],
  "order_type_dist": [
    { "type": "combo",  "label": "套餐",   "count": 80 },
    { "type": "custom", "label": "自选餐", "count": 40 }
  ],
  "channel_dist": [
    { "channel": "wechat", "label": "微信支付", "count": 90 }
  ],
  "hourly_dist": [
    { "hour": 11, "label": "11时", "count": 45 }
  ],
  "session_summary": [
    { "session_id": 1, "name": "7月2日 中午场", "count": 22, "revenue": 318.0 }
  ]
}
```

**字段说明：**

| 字段 | 说明 |
|------|------|
| `summary` | 汇总指标：总订单数、已完成数、总收入、待处理数、平均客单价 |
| `status_dist` | 各状态订单数分布 |
| `revenue_trend` | 收入趋势（今天→按小时；本周→按天；本月→按日；全部→按自然日）|
| `top_dishes` | 热门菜品 Top 10（排除米饭）|
| `combo_dist` | 各套餐类型销售数量 |
| `pickup_dist` | 各取餐点订单数（无取餐点 ID 的显示地址文本）|
| `order_type_dist` | 套餐 vs 自选比例 |
| `channel_dist` | 支付渠道分布（微信/支付宝/现金）|
| `hourly_dist` | 0-23时下单时段分布（始终返回 24 条）|
| `session_summary` | 各餐次订单汇总（仅在未按餐次筛选时返回）|

---

## 健康检查

```
GET /api/health
```

```json
{ "status": "ok" }
```

---

## 非 API 路由（静态页面托管）

| 路径 | 说明 |
|------|------|
| `GET /` | 托管 `frontend/index.html`（用户点餐端）|
| `GET /admin` | 托管 `admin/index.html`（管理后台）|
