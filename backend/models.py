from flask_sqlalchemy import SQLAlchemy
from datetime import datetime

db = SQLAlchemy()


class User(db.Model):
    __tablename__ = 'users'
    id            = db.Column(db.Integer, primary_key=True)
    name          = db.Column(db.String(50),  nullable=False)
    phone         = db.Column(db.String(20),  unique=True, nullable=False)
    password_hash = db.Column(db.String(256), nullable=False)
    class_name    = db.Column(db.String(50),  default='')   # 备注
    created_at    = db.Column(db.DateTime, default=datetime.utcnow)
    orders        = db.relationship('Order', backref='user', lazy=True)

    def to_dict(self):
        return {'id': self.id, 'name': self.name, 'phone': self.phone, 'class_name': self.class_name or ''}


class Admin(db.Model):
    __tablename__ = 'admins'
    id            = db.Column(db.Integer, primary_key=True)
    username      = db.Column(db.String(50), unique=True, nullable=False)
    password_hash = db.Column(db.String(256), nullable=False)


class MenuItem(db.Model):
    __tablename__ = 'menu_items'
    id           = db.Column(db.Integer, primary_key=True)
    name         = db.Column(db.String(50),  nullable=False)
    category     = db.Column(db.String(10),  nullable=False)  # 荤 / 素
    price        = db.Column(db.Float,       nullable=False)
    is_available = db.Column(db.Boolean,     default=True)
    emoji        = db.Column(db.String(10),  default='🍽️')

    def to_dict(self):
        return {
            'id': self.id, 'name': self.name, 'category': self.category,
            'price': self.price, 'is_available': self.is_available, 'emoji': self.emoji,
        }


class ComboType(db.Model):
    __tablename__ = 'combo_types'
    id          = db.Column(db.Integer, primary_key=True)
    name        = db.Column(db.String(50),  nullable=False)
    meat_count  = db.Column(db.Integer,     nullable=False)
    veg_count   = db.Column(db.Integer,     nullable=False)
    price       = db.Column(db.Float,       nullable=False)
    description = db.Column(db.String(200), default='')
    is_featured = db.Column(db.Boolean,     default=False)  # 是否为推荐套餐（前端默认展示）

    def to_dict(self):
        return {
            'id': self.id, 'name': self.name,
            'meat_count': self.meat_count, 'veg_count': self.veg_count,
            'price': self.price, 'description': self.description,
            'is_featured': self.is_featured,
        }


class PickupPoint(db.Model):
    __tablename__ = 'pickup_points'
    id         = db.Column(db.Integer,     primary_key=True)
    name       = db.Column(db.String(100), nullable=False)
    location   = db.Column(db.String(200), nullable=False)
    open_time  = db.Column(db.String(100), default='')
    note       = db.Column(db.String(200), default='')
    is_active  = db.Column(db.Boolean,     default=True)
    updated_at = db.Column(db.DateTime,    default=datetime.utcnow, onupdate=datetime.utcnow)

    def to_dict(self):
        return {
            'id': self.id, 'name': self.name, 'location': self.location,
            'open_time': self.open_time, 'note': self.note,
            'is_active': self.is_active,
            'updated_at': self.updated_at.strftime('%Y-%m-%d %H:%M:%S'),
        }


class OrderSession(db.Model):
    """点餐餐次：控制某时段内用户可以下单"""
    __tablename__ = 'order_sessions'
    id           = db.Column(db.Integer, primary_key=True)
    name         = db.Column(db.String(100), nullable=False)      # 如"7月2日 中午场"
    order_start  = db.Column(db.DateTime,    nullable=False)       # 开始下单时间
    order_end    = db.Column(db.DateTime,    nullable=False)       # 截止下单时间
    deliver_time = db.Column(db.String(50),  default='')           # 预计送餐时间描述
    note         = db.Column(db.String(200), default='')
    is_active    = db.Column(db.Boolean,     default=True)
    created_at   = db.Column(db.DateTime,    default=datetime.utcnow)

    def get_status(self):
        now = datetime.now()  # 使用本地时间，与存入的时间保持一致
        if not self.is_active:
            return 'closed'
        if now < self.order_start:
            return 'upcoming'
        if now > self.order_end:
            return 'ended'
        return 'open'

    def is_open(self):
        return self.get_status() == 'open'

    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'order_start':  self.order_start.strftime('%Y-%m-%d %H:%M'),
            'order_end':    self.order_end.strftime('%Y-%m-%d %H:%M'),
            'deliver_time': self.deliver_time,
            'note':         self.note,
            'is_active':    self.is_active,
            'status':       self.get_status(),
            'created_at':   self.created_at.strftime('%Y-%m-%d %H:%M:%S'),
        }


class Order(db.Model):
    __tablename__ = 'orders'
    __table_args__ = (
        db.Index('ix_orders_user_id',    'user_id'),
        db.Index('ix_orders_session_id', 'session_id'),
        db.Index('ix_orders_status',     'status'),
        db.Index('ix_orders_created_at', 'created_at'),
    )
    id               = db.Column(db.Integer, primary_key=True)
    user_id          = db.Column(db.Integer, db.ForeignKey('users.id'),          nullable=False)
    session_id       = db.Column(db.Integer, db.ForeignKey('order_sessions.id'), nullable=True)
    pickup_point_id  = db.Column(db.Integer, db.ForeignKey('pickup_points.id'),  nullable=True)
    order_type       = db.Column(db.String(10),  nullable=False)   # combo / custom
    combo_type_id    = db.Column(db.Integer, db.ForeignKey('combo_types.id'), nullable=True)
    total_price      = db.Column(db.Float,   nullable=False)
    status           = db.Column(db.String(20), default='unpaid')  # unpaid→pending→preparing→delivering→delivered
    payment_note     = db.Column(db.String(100), default='')       # 转账备注/单号
    payment_channel  = db.Column(db.String(20),  default='wechat') # 支付渠道：wechat / alipay
    note             = db.Column(db.String(200), default='')
    address          = db.Column(db.String(100), default='')
    created_at       = db.Column(db.DateTime, default=datetime.utcnow)
    # joinedload：一次 JOIN 查出关联数据，避免 N+1
    items        = db.relationship('OrderItem',    backref='order',  lazy='joined')
    session      = db.relationship('OrderSession', backref='orders', lazy='joined',
                                   foreign_keys=[session_id])
    pickup_point = db.relationship('PickupPoint',  backref='orders', lazy='joined',
                                   foreign_keys=[pickup_point_id])

    def to_dict(self):
        # combo_type 通过 combo_type_id 关联，用 identity map 命中缓存，无额外查询
        combo = None
        if self.combo_type_id:
            ct = db.session.get(ComboType, self.combo_type_id)
            combo = ct.to_dict() if ct else None
        pickup = self.pickup_point
        return {
            'id': self.id,
            'user_id': self.user_id,
            'user': self.user.to_dict() if self.user else None,
            'session_id':        self.session_id,
            'session_name':      self.session.name if self.session else None,
            'pickup_point_id':   self.pickup_point_id,
            'pickup_point_name': pickup.name if pickup else None,
            'order_type': self.order_type,
            'combo': combo,
            'total_price': self.total_price,
            'status': self.status,
            'payment_note': self.payment_note,
            'payment_channel': self.payment_channel or 'wechat',
            'note': self.note,
            'address': self.address,
            'created_at': self.created_at.strftime('%Y-%m-%d %H:%M:%S'),
            'items': [item.to_dict() for item in self.items],
        }


class OrderItem(db.Model):
    __tablename__ = 'order_items'
    __table_args__ = (
        db.Index('ix_order_items_order_id',     'order_id'),
        db.Index('ix_order_items_menu_item_id', 'menu_item_id'),
    )
    id           = db.Column(db.Integer, primary_key=True)
    order_id     = db.Column(db.Integer, db.ForeignKey('orders.id'),     nullable=False)
    menu_item_id = db.Column(db.Integer, db.ForeignKey('menu_items.id'), nullable=False)
    quantity     = db.Column(db.Integer, default=1)
    price        = db.Column(db.Float,   nullable=False)
    # joinedload：取 order_items 时一并取出 menu_item，避免每行单独查询
    menu_item    = db.relationship('MenuItem', lazy='joined', foreign_keys=[menu_item_id])

    def to_dict(self):
        item = self.menu_item
        return {
            'id': self.id,
            'menu_item_id': self.menu_item_id,
            'name':     item.name     if item else '已删除',
            'emoji':    item.emoji    if item else '🍽️',
            'category': item.category if item else '',
            'quantity': self.quantity,
            'price':    self.price,
        }


class SystemConfig(db.Model):
    """系统配置：key-value 存储，收款码等全局配置"""
    __tablename__ = 'system_config'
    id         = db.Column(db.Integer,    primary_key=True)
    key        = db.Column(db.String(50), unique=True, nullable=False)
    value      = db.Column(db.Text,       nullable=False, default='')
    updated_at = db.Column(db.DateTime,   default=datetime.utcnow, onupdate=datetime.utcnow)

    @staticmethod
    def get(key, default=''):
        row = SystemConfig.query.filter_by(key=key).first()
        return row.value if row else default

    @staticmethod
    def set(key, value):
        row = SystemConfig.query.filter_by(key=key).first()
        if row:
            row.value = value
            row.updated_at = datetime.utcnow()
        else:
            row = SystemConfig(key=key, value=value)
            db.session.add(row)
        db.session.commit()

    def to_dict(self):
        return {'key': self.key, 'value': self.value}

