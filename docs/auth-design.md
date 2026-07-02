# 认证与权限设计

## 认证方案

采用 **JWT（JSON Web Token）无状态认证**，服务端不存储 Session，Token 由客户端保存并随每次请求携带。  
算法：HS256，密钥长度建议 ≥ 32 字节。

---

## Token 生成

```python
# auth.py
def make_token(user_id, role):
    payload = {
        'user_id': user_id,
        'role': role,          # 'student' 或 'admin'
        'exp': datetime.datetime.utcnow() + datetime.timedelta(days=30),
        # 管理员登录时用 timedelta(days=7)
    }
    return jwt.encode(payload, SECRET_KEY, algorithm='HS256')
```

**密钥配置**（`backend/config.py`）：

```python
import os
SECRET_KEY = os.environ.get('FOOD_SECRET_KEY', 'campus-food-order-secret-2024')
```

> ⚠️ 生产环境必须设置 `FOOD_SECRET_KEY` 环境变量，建议用 `python -c "import secrets; print(secrets.token_hex(32))"` 生成。

---

## Token 验证流程

```
客户端请求
    │
    ├─ Header: Authorization: Bearer <token>
    │
    ▼
utils._decode_token()
    ├─ 无 Header / 格式非 "Bearer " → 返回 (None, 'missing_token') → 401
    ├─ jwt.ExpiredSignatureError → 返回 (None, 'token_expired') → 401
    └─ jwt.InvalidTokenError    → 返回 (None, 'invalid_token')  → 401
    │
    ▼ 解码成功，得到 payload = {user_id, role, exp}
    │
    ├─ @student_required：检查 role != 'student' → 403
    │       ↓ 通过
    │   User.query.get(payload['user_id']) 为 None → 401
    │       ↓ 通过
    │   将 user 对象注入视图函数第一参数
    │
    └─ @admin_required：检查 role != 'admin' → 403
            ↓ 通过
        Admin.query.get(payload['user_id']) 为 None → 401
            ↓ 通过
        执行业务逻辑
```

---

## 权限分层

| 接口前缀 | 装饰器 | 允许角色 | 说明 |
|---------|--------|---------|------|
| `GET /api/menu/*` | 无 | 所有人 | 菜单/套餐/取餐点/餐次/收款码/联系方式 |
| `POST /api/auth/register` | 无 | 所有人 | 注册 |
| `POST /api/auth/login` | 无 | 所有人 | 用户登录 |
| `POST /api/admin/login` | 无 | 所有人 | 管理员登录 |
| `GET /api/auth/me` | `_decode_token`（手动调用）| student | 获取个人信息 |
| `PUT /api/auth/me` | `_decode_token`（手动调用）| student | 修改个人信息 |
| `POST /api/orders` | `@student_required` | student | 下单 |
| `GET /api/orders/my` | `@student_required` | student | 我的订单 |
| `GET/PUT/POST/DELETE /api/admin/*`（除 login）| `@admin_required` | admin | 管理员全部操作 |
| `GET /api/admin/stats` | `@admin_required` | admin | 统计分析 |

---

## 装饰器实现（`backend/utils.py`）

```python
def _decode_token():
    """从 Authorization Header 解码 JWT，返回 (payload, None) 或 (None, error_code)"""
    auth = request.headers.get('Authorization', '')
    if not auth.startswith('Bearer '):
        return None, 'missing_token'
    token = auth[7:]
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=['HS256'])
        return payload, None
    except jwt.ExpiredSignatureError:
        return None, 'token_expired'
    except jwt.InvalidTokenError:
        return None, 'invalid_token'


def student_required(f):
    """用户身份验证装饰器，通过后将 current_user 注入视图函数第一参数"""
    @wraps(f)
    def decorated(*args, **kwargs):
        payload, err = _decode_token()
        if err:
            return jsonify({'error': '请先登录'}), 401
        if payload.get('role') != 'student':
            return jsonify({'error': '权限不足'}), 403
        user = User.query.get(payload['user_id'])
        if not user:
            return jsonify({'error': '用户不存在'}), 401
        return f(user, *args, **kwargs)   # current_user 注入第一参数
    return decorated


def admin_required(f):
    """管理员身份验证装饰器，额外查库验证账号仍存在"""
    @wraps(f)
    def decorated(*args, **kwargs):
        payload, err = _decode_token()
        if err:
            return jsonify({'error': '请先登录'}), 401
        if payload.get('role') != 'admin':
            return jsonify({'error': '权限不足'}), 403
        # 验证 admin 在数据库中仍存在（防止被删后 token 仍有效）
        if not Admin.query.get(payload['user_id']):
            return jsonify({'error': '账号不存在'}), 401
        return f(*args, **kwargs)
    return decorated
```

---

## 客户端存储策略

| 数据 | localStorage Key | 说明 |
|------|----------------|------|
| 用户 Token | `token` | 30 天有效，页面刷新后自动恢复登录 |
| 用户信息 | `user` | JSON 序列化，含 `id`/`name`/`phone`/`class_name` |
| 管理员 Token | `adminToken` | 7 天有效，独立 key 与用户 Token 不冲突 |
| 记住密码 | `saved_login` | `{phone, pwd}` 明文存储，仅用户勾选"记住密码"时写入 |

退出登录时清除 Token 和用户信息，但保留 `saved_login`（如已勾选）。  
切换到其他 Tab（非订单页）时停止 30 秒定时器；切回订单页时恢复，避免内存泄漏。

---

## 个人信息管理

用户可通过"👤 资料"按钮打开底部弹窗，调用 `PUT /api/auth/me` 修改：

| 操作 | 条件 |
|------|------|
| 修改姓名、备注 | 无条件可改（备注可改为空字符串）|
| 修改密码 | 需提供正确的旧密码；新密码 ≥ 6 位 |

提交成功后前端更新 `localStorage.user` 本地缓存，顶部栏实时刷新显示名。

---

## 安全说明

| 项目 | 当前状态 | 生产建议 |
|------|---------|---------|
| JWT 密钥 | 支持环境变量 `FOOD_SECRET_KEY`，有默认值兜底 | ✅ 生产环境设置强随机密钥 |
| 密码存储 | Werkzeug pbkdf2:sha256 哈希（自动加盐）| ✅ 安全 |
| Token 存储位置 | `localStorage` | 可改用 `httpOnly Cookie` 防 XSS |
| HTTPS | 未启用（本地开发）| 生产环境必须启用 |
| 记住密码 | 明文存 `localStorage.saved_login` | 生产环境建议去掉此功能 |
| Token 撤销 | 不支持（无状态，需等待自然过期）| 如需强制登出，可加 Token 黑名单（Redis）|
| admin 账号存在性 | `admin_required` 每次请求都查库验证 | ✅ 防止被删后 Token 仍有效 |
| 调试模式 | 由环境变量 `FLASK_DEBUG` 控制（默认开启）| 生产环境设置 `FLASK_DEBUG=0` |
