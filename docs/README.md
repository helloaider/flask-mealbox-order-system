# 文档目录

> 本目录包含系统的全套设计与开发文档，均根据实际代码反推整理，与实现保持一致。

---

## 文档列表

| 文件 | 内容 |
|------|------|
| [api.md](./api.md) | 全量 REST API 接口文档（请求/响应格式、字段说明、错误码）|
| [data-model.md](./data-model.md) | 数据模型（ER 图、表结构、ORM 关系、业务约束）|
| [architecture.md](./architecture.md) | 系统架构（技术选型、目录结构、关键设计决策）|
| [auth-design.md](./auth-design.md) | 认证与权限设计（JWT 流程、装饰器实现、客户端存储策略）|
| [business-logic.md](./business-logic.md) | 业务逻辑（下单流程、支付流程、价格规则、校验规则）|
| [frontend-design.md](./frontend-design.md) | 前端设计（页面结构、组件行为、响应式、设计规范）|
| [optimization.md](./optimization.md) | 代码审查与优化记录（问题清单、修复状态）|
| [lessons-learned.md](./lessons-learned.md) | 经验教训复盘（设计决策、踩坑记录、可复用结论）|

---

## 快速索引

**想了解整体设计** → `architecture.md`

**查某个 API 的请求格式** → `api.md`

**看数据库表结构** → `data-model.md`

**了解登录/权限逻辑** → `auth-design.md`

**理解下单和定价规则** → `business-logic.md`

**查前端组件/样式规范** → `frontend-design.md`

**了解已知问题和优化** → `optimization.md`

**复盘设计经验** → `lessons-learned.md`

---

## 与代码的对应关系

```
docs/api.md          ←→  backend/routes/{auth,menu,orders,admin,stats}.py
docs/data-model.md   ←→  backend/models.py
docs/architecture.md ←→  backend/app.py + 目录结构
docs/auth-design.md  ←→  backend/utils.py + backend/config.py
docs/business-logic.md ←→ backend/routes/orders.py + routes/admin.py
docs/frontend-design.md ←→ frontend/index.html + admin/index.html
```
