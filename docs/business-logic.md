# 业务逻辑设计

## 核心业务流程

### 用户下单流程

```
用户打开页面
    │
    ├─ 未登录 → 注册/登录（支持"记住密码"勾选框）
    │
    ▼ 登录成功
showMain() 立即展示页面框架（非阻塞）
    │
    ▼ 后台异步加载（不阻塞界面）
并行请求：菜单 / 套餐 / 取餐点 / 餐次状态
    │
    ├─ 无开放餐次（is_open=false）
    │   → 点餐区锁定，显示"当前不在点餐时间"
    │
    ▼ 加载完成，展示点餐界面
    │
    ├─ 套餐下单
    │   ├─ 推荐套餐（is_featured=True）默认展示
    │   ├─ 其余套餐折叠在"▼ 查看更多（N个）"后
    │   └─ 点击套餐卡片 → 选中套餐 → 打开购物车抽屉
    │
    └─ 自由选菜
        ├─ 分荤菜 / 素菜两栏展示
        └─ 调整数量 → 底部购物车栏实时更新 → 点击打开购物车抽屉
    │
    ▼ 购物车抽屉
    ├─ 有多个开放/upcoming 餐次时：展示餐次选择器
    ├─ 取餐点下拉卡片（只有一个时自动默认选中）
    ├─ 备注输入（选填）
    ├─ 收款码展示（GET /api/menu/qrcode）
    ├─ 选择支付渠道（微信/支付宝）
    ├─ 填写转账备注（手机号后四位）
    └─ 点击"已付款，提交订单"
    │
    ▼
POST /api/orders → 成功
    │
    └─ 弹窗显示订单号和金额 → 清空购物车 → "我的订单"可查看状态
```

---

### 套餐随机搭配

下单时后端从可用菜品池中随机抽取：

```python
meats = MenuItem.query.filter_by(category='荤', is_available=True).all()
vegs  = MenuItem.query.filter_by(category='素', is_available=True).all()

if len(meats) < combo.meat_count or len(vegs) < combo.veg_count:
    return 400  # 可用菜品不足，拒单

chosen = random.sample(meats, combo.meat_count) + random.sample(vegs, combo.veg_count)
```

- 每次下单独立随机（无固定种子），同一套餐每次搭配可能不同
- `random.sample` 保证不重复抽取（不会出现两份同一道菜）
- 随机结果写入 `OrderItem`，用户在订单详情中可看到具体搭配

---

### 管理员处理订单流程

```
新订单（status=unpaid）
    │  管理员后台每 30 秒自动刷新
    │
    ▼
管理员核对转账记录：金额是否正确 + payment_note 是否匹配
    │
    ▼ 点击"💰 确认收款"
POST /api/admin/orders/<id>/confirm_payment
    │  status → pending
    ▼
点击"✅ 接单制作"
    │  status → preparing
    ▼
制作完成，点击"🛵 开始配送"
    │  status → delivering
    ▼
送达，点击"✔️ 确认送达"
    │  status → delivered（终态）
    ▼
```

**批量操作**：勾选多个同状态订单，底部浮动栏出现批量按钮，点击后 `Promise.all` 并行发请求，统一显示 loading，全部完成后刷新列表。

> 状态机严格单向，`delivered` 后无法回退，任何逆向切换后端返回 400。

---

## 支付流程

```
用户：购物车抽屉加载收款码
    │  GET /api/menu/qrcode（无需登录）
    ▼
选择支付渠道（微信/支付宝）→ 展示对应收款码图片 + 金额
    │
用户线下扫码转账，备注填手机号后四位
    │
    ▼
提交订单，payment_note（转账备注）+ payment_channel（渠道）写入数据库
status = unpaid
    │
    ▼
管理员后台：筛选 unpaid 订单
    │
核对转账金额 ✓ + payment_note 与用户手机号后四位一致 ✓
    │
点击"💰 确认收款"
POST /api/admin/orders/<id>/confirm_payment
    │  status unpaid → pending
    ▼ 进入制作流程
```

**收款码存储**：Base64 图片存入 `system_config` 表（`qr_wechat` / `qr_alipay`），所有设备共享，前端同时缓存到 `localStorage`（减少重复请求）。

---

## 套餐推荐折叠机制

```
is_featured = True  → 推荐套餐，默认可见，右上角"★ 推荐"橙色标签
is_featured = False → 折叠在"▼ 查看更多套餐（N个）"按钮后

特殊情况：所有套餐均无推荐（全为 False）→ 全量展示，无折叠按钮（兼容旧数据）
```

管理员切换推荐状态：`POST /api/admin/combos/<id>/featured`，每次调用取反（无请求体）。  
建议推荐数量：3~6 个，覆盖最常用荤素组合。  
折叠区用 CSS `max-height` 过渡实现平滑展开/收起动画。

---

## 餐次管理与点餐控制

**状态计算（服务端使用本地时间 `datetime.now()`）：**

```python
def get_status(self):
    now = datetime.now()
    if not self.is_active:     return 'closed'
    if now < self.order_start: return 'upcoming'
    if now > self.order_end:   return 'ended'
    return 'open'
```

**前端轮询控制点餐开关：**

- 每 60 秒静默轮询 `GET /api/menu/session`（不显示 loading 菊花）
- `is_open=false` → 点餐区锁定，底部购物车栏隐藏，显示"当前不在点餐时间"提示
- `is_open=true` → 恢复正常点餐，用户无需手动刷新

**预约功能**：用户可在购物车抽屉选择 `upcoming`（尚未开始）的餐次提前锁定，后端允许此操作（`order_end >= now` 即可）。

---

## 价格结算规则

### 定价公式

```
total = 10 + 荤菜数 × 2 + 素菜数 × 1
      = (底座8元 + 米饭2元) + 荤菜数×2元 + 素菜数×1元
```

| 套餐示例 | 荤 | 素 | 价格 |
|---------|----|----|------|
| 一素套餐 | 0 | 1 | ¥11 |
| 一荤一素套餐 | 1 | 1 | ¥13 |
| 两荤两素套餐 | 2 | 2 | ¥16 |
| 三荤三素套餐 | 3 | 3 | ¥19 |

### 套餐下单

价格固定为 `ComboType.price`（后端读取，不重新计算），最终写入 `Order.total_price`。

### 自由选菜

按公式实时计算，忽略菜品单价：

```python
total = round(10.0 + meat_count * 2.0 + veg_count * 1.0, 2)
```

前端同步展示估算金额（实时根据购物车内荤素数量计算）。

### 米饭自动附带

```python
rice = MenuItem.query.filter_by(name='米饭', is_available=True).first()
if rice:
    db.session.add(OrderItem(
        order_id=order.id, menu_item_id=rice.id, quantity=1, price=rice.price
    ))
```

米饭价格（2.0元）已含在总价公式底座中，`OrderItem.price` 记录实际单价用于展示。

### 价格快照

`OrderItem.price` 下单时固定，后续菜品改价不影响历史订单金额。  
（自由选菜的明细 `price=0.0`，实际金额由 `Order.total_price` 记录）

---

## 菜品生命周期

```
上架（is_available=True）
    │  管理员后台点"下架"
    ▼
下架（is_available=False）
    ├─ 不出现在 GET /api/menu 返回的菜品列表
    ├─ 不进入套餐随机抽取池
    │   （如可用菜品不足 combo.meat_count 或 veg_count 则拒单）
    └─ 历史 OrderItem 仍保留关联
        └─ OrderItem.to_dict() 中 name 显示"已删除"
```

不支持物理删除，防止历史订单外键失效。

---

## 输入校验规则

### 用户注册（`POST /api/auth/register`）

| 字段 | 规则 |
|------|------|
| name | 非空（strip 后）|
| phone | 非空、11 位纯数字、数据库中唯一 |
| password | 非空（不 strip，保留原始输入）|
| class_name | 选填，空字符串也接受 |

### 修改个人信息（`PUT /api/auth/me`）

| 字段 | 规则 |
|------|------|
| name | 非空 |
| class_name | 选填 |
| new_password | 提供时：≥ 6 位；同时必须提供正确的 old_password |

### 提交订单（`POST /api/orders`）

| 字段 | 规则 |
|------|------|
| order_type | `combo` 或 `custom` |
| combo_type_id | combo 时必填，且套餐必须存在 |
| items | custom 时至少 1 个有效菜品（`is_available=True`），主食自动忽略，quantity ≥ 1 |
| pickup_point_id / address | 二选一；pickup_point 必须 `is_active=True` |
| session_id | 未指定则自动取当前开放餐次；指定时餐次不能是 `ended` |
| 防重复 | 同用户同餐次已有非 `delivered` 订单时拒绝 |
| 菜品充足 | 套餐下单时可用荤/素菜数量必须满足 combo.meat_count / veg_count |

### 管理员操作

| 接口 | 规则 |
|------|------|
| 新增菜品 | name 非空，category 为 `荤` 或 `素` |
| 编辑订单状态 | status 在合法值内，且符合状态机流转规则 |
| 新增套餐 | name/meat_count/veg_count/price 非空，总菜数 ≥ 1，meat ≥ 0，veg ≥ 0 |
| 新增取餐点 | name 和 location 非空 |
| 新增餐次 | name/order_start/order_end 非空，时间格式合法，截止 > 开始 |
| 保存收款码 | image 必须以 `data:image/` 开头 |

---

## 管理后台自动刷新策略

| 功能 | 刷新方式 | 触发条件 |
|------|---------|---------|
| 订单列表 | 30 秒定时器 | 停留在订单面板时持续运行；切换到其他面板时暂停，切回恢复 |
| 餐次状态 | 60 秒定时器（前端用户端）| 始终后台运行，不显示 loading |
| 统计数据 | 手动（切换 range / session_id 时）| 不自动刷新 |
