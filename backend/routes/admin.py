from flask import Blueprint, request, jsonify
from werkzeug.security import check_password_hash
import jwt
import datetime
from models import db, Admin, Order, OrderItem, MenuItem, ComboType, PickupPoint, OrderSession, SystemConfig
from sqlalchemy.orm import joinedload
from utils import admin_required
from config import SECRET_KEY

admin_bp = Blueprint('admin', __name__)


@admin_bp.route('/login', methods=['POST'])
def admin_login():
    data = request.get_json()
    username = (data.get('username') or '').strip()
    password = (data.get('password') or '').strip()

    admin = Admin.query.filter_by(username=username).first()
    if not admin or not check_password_hash(admin.password_hash, password):
        return jsonify({'error': '用户名或密码错误'}), 401

    payload = {
        'user_id': admin.id,
        'role': 'admin',
        'exp': datetime.datetime.now() + datetime.timedelta(days=7),
    }
    token = jwt.encode(payload, SECRET_KEY, algorithm='HS256')
    return jsonify({'token': token, 'username': admin.username}), 200


@admin_bp.route('/orders', methods=['GET'])
@admin_required
def get_orders():
    from models import User
    status     = request.args.get('status')
    session_id = request.args.get('session_id')
    q          = request.args.get('q', '').strip()   # 搜索关键词

    query = Order.query.order_by(Order.created_at.desc())
    if status:
        query = query.filter_by(status=status)
    if session_id:
        query = query.filter_by(session_id=int(session_id))

    # 关键词搜索：订单号 / 地址 / 备注 / 姓名 / 手机号
    if q:
        if q.isdigit():
            query = query.filter(Order.id == int(q))
        else:
            from sqlalchemy import or_
            from models import User
            query = query.join(User, Order.user_id == User.id).filter(
                or_(
                    Order.address.ilike(f'%{q}%'),
                    Order.note.ilike(f'%{q}%'),
                    User.name.ilike(f'%{q}%'),
                    User.phone.ilike(f'%{q}%'),
                )
            )

    orders = (
        query
        .options(
            joinedload(Order.items).joinedload(OrderItem.menu_item),
            joinedload(Order.session),
            joinedload(Order.pickup_point),
        )
        .all()
    )
    return jsonify([o.to_dict() for o in orders])


@admin_bp.route('/orders/<int:order_id>/status', methods=['PUT'])
@admin_required
def update_order_status(order_id):
    data = request.get_json()
    new_status = data.get('status')
    valid = ['unpaid', 'pending', 'preparing', 'delivering', 'delivered']
    if new_status not in valid:
        return jsonify({'error': '无效状态'}), 400

    # 状态机：只允许向前流转，不允许回退
    FLOW = {
        'unpaid':     ['pending'],
        'pending':    ['preparing', 'delivering', 'delivered'],
        'preparing':  ['delivering', 'delivered'],
        'delivering': ['delivered'],
        'delivered':  [],
    }
    order = Order.query.get_or_404(order_id)
    allowed = FLOW.get(order.status, [])
    if new_status not in allowed:
        return jsonify({'error': f'不允许从 {order.status} 切换到 {new_status}'}), 400

    order.status = new_status
    db.session.commit()
    return jsonify(order.to_dict())


@admin_bp.route('/orders/<int:order_id>/confirm_payment', methods=['POST'])
@admin_required
def confirm_payment(order_id):
    """确认收款：unpaid → pending"""
    order = Order.query.get_or_404(order_id)
    if order.status != 'unpaid':
        return jsonify({'error': '该订单不是待收款状态'}), 400
    order.status = 'pending'
    db.session.commit()
    return jsonify(order.to_dict())


@admin_bp.route('/menu', methods=['GET'])
@admin_required
def get_menu():
    items = MenuItem.query.all()
    return jsonify([i.to_dict() for i in items])


@admin_bp.route('/menu', methods=['POST'])
@admin_required
def add_menu_item():
    data = request.get_json()
    name     = (data.get('name') or '').strip()
    category = (data.get('category') or '').strip()
    emoji    = data.get('emoji', '🍽️')

    if not name or category not in ('荤', '素'):
        return jsonify({'error': '参数有误'}), 400

    # 价格字段保留（兼容性），但计费不使用，统一为0
    item = MenuItem(name=name, category=category, price=0.0, emoji=emoji)
    db.session.add(item)
    db.session.commit()
    return jsonify(item.to_dict()), 201


@admin_bp.route('/menu/<int:item_id>', methods=['PUT'])
@admin_required
def update_menu_item(item_id):
    item = MenuItem.query.get_or_404(item_id)
    data = request.get_json()
    if 'name' in data:
        item.name = data['name']
    if 'price' in data:
        item.price = float(data['price'])
    if 'is_available' in data:
        item.is_available = bool(data['is_available'])
    if 'emoji' in data:
        item.emoji = data['emoji']
    db.session.commit()
    return jsonify(item.to_dict())


@admin_bp.route('/menu/<int:item_id>', methods=['DELETE'])
@admin_required
def delete_menu_item(item_id):
    item = MenuItem.query.get_or_404(item_id)
    item.is_available = False
    db.session.commit()
    return jsonify({'message': '已下架'})


@admin_bp.route('/combos', methods=['GET'])
@admin_required
def get_combos():
    combos = ComboType.query.order_by(ComboType.meat_count, ComboType.veg_count).all()
    return jsonify([c.to_dict() for c in combos])


@admin_bp.route('/combos', methods=['POST'])
@admin_required
def add_combo():
    data = request.get_json()
    name       = (data.get('name') or '').strip()
    meat_count = data.get('meat_count')
    veg_count  = data.get('veg_count')
    price      = data.get('price')
    description = (data.get('description') or '').strip()

    if not name or meat_count is None or veg_count is None or price is None:
        return jsonify({'error': '名称、荤菜数、素菜数、价格为必填'}), 400
    if int(meat_count) < 0 or int(veg_count) < 0 or (int(meat_count) + int(veg_count)) < 1:
        return jsonify({'error': '菜品数量有误'}), 400

    combo = ComboType(
        name=name,
        meat_count=int(meat_count),
        veg_count=int(veg_count),
        price=float(price),
        description=description,
    )
    db.session.add(combo)
    db.session.commit()
    return jsonify(combo.to_dict()), 201


@admin_bp.route('/combos/<int:cid>', methods=['PUT'])
@admin_required
def update_combo(cid):
    combo = ComboType.query.get_or_404(cid)
    data  = request.get_json()
    if 'name' in data:        combo.name        = data['name'].strip()
    if 'meat_count' in data:  combo.meat_count  = int(data['meat_count'])
    if 'veg_count' in data:   combo.veg_count   = int(data['veg_count'])
    if 'price' in data:       combo.price       = float(data['price'])
    if 'description' in data: combo.description = data['description'].strip()
    if 'is_featured' in data: combo.is_featured = bool(data['is_featured'])
    db.session.commit()
    return jsonify(combo.to_dict())


@admin_bp.route('/combos/<int:cid>/featured', methods=['POST'])
@admin_required
def toggle_combo_featured(cid):
    """切换套餐是否为推荐（前端默认展示）"""
    combo = ComboType.query.get_or_404(cid)
    combo.is_featured = not combo.is_featured
    db.session.commit()
    return jsonify(combo.to_dict())


@admin_bp.route('/combos/<int:cid>', methods=['DELETE'])
@admin_required
def delete_combo(cid):
    combo = ComboType.query.get_or_404(cid)
    db.session.delete(combo)
    db.session.commit()
    return jsonify({'message': '已删除'})


@admin_bp.route('/combos/calc-price', methods=['GET'])
@admin_required
def calc_combo_price():
    """动态计算推荐价格。规则：底座8元 + 米饭2元 + 荤×2 + 素×1 = 10 + 荤×2 + 素×1（含饭）"""
    try:
        meat = int(request.args.get('meat', 0))
        veg  = int(request.args.get('veg', 0))
    except (ValueError, TypeError):
        return jsonify({'error': '参数有误'}), 400
    if meat < 0 or veg < 0 or (meat + veg) < 1:
        return jsonify({'error': '菜品数量有误'}), 400
    price = 10.0 + meat * 2.0 + veg * 1.0
    return jsonify({'meat': meat, 'veg': veg, 'price': price})


# ── 取餐点管理 ──────────────────────────────────────────
@admin_bp.route('/pickup', methods=['GET'])
@admin_required
def get_pickup():
    points = PickupPoint.query.all()
    return jsonify([p.to_dict() for p in points])


@admin_bp.route('/pickup', methods=['POST'])
@admin_required
def add_pickup():
    data = request.get_json()
    name = (data.get('name') or '').strip()
    location = (data.get('location') or '').strip()
    if not name or not location:
        return jsonify({'error': '名称和地点为必填'}), 400
    p = PickupPoint(
        name=name,
        location=location,
        open_time=data.get('open_time', '').strip(),
        note=data.get('note', '').strip(),
    )
    db.session.add(p)
    db.session.commit()
    return jsonify(p.to_dict()), 201


@admin_bp.route('/pickup/<int:pid>', methods=['PUT'])
@admin_required
def update_pickup(pid):
    p = PickupPoint.query.get_or_404(pid)
    data = request.get_json()
    if 'name' in data:      p.name = data['name'].strip()
    if 'location' in data:  p.location = data['location'].strip()
    if 'open_time' in data: p.open_time = data['open_time'].strip()
    if 'note' in data:      p.note = data['note'].strip()
    if 'is_active' in data: p.is_active = bool(data['is_active'])
    p.updated_at = datetime.datetime.now()
    db.session.commit()
    return jsonify(p.to_dict())


@admin_bp.route('/pickup/<int:pid>', methods=['DELETE'])
@admin_required
def delete_pickup(pid):
    p = PickupPoint.query.get_or_404(pid)
    db.session.delete(p)
    db.session.commit()
    return jsonify({'message': '已删除'})


# ── 餐次管理 ─────────────────────────────────────────────
def _parse_dt(raw):
    """解析时间字符串，支持 YYYY-MM-DD HH:MM、YYYY/MM/DD HH:MM、YYYY-MM-DDTHH:MM 等格式"""
    import datetime as dt
    s = raw.strip().replace('/', '-').replace('T', ' ')[:16]
    return dt.datetime.strptime(s, '%Y-%m-%d %H:%M')
@admin_bp.route('/sessions', methods=['GET'])
@admin_required
def get_sessions():
    sessions = OrderSession.query.order_by(OrderSession.order_start.desc()).all()
    return jsonify([s.to_dict() for s in sessions])


@admin_bp.route('/sessions', methods=['POST'])
@admin_required
def create_session():
    data = request.get_json()
    name = (data.get('name') or '').strip()
    order_start = data.get('order_start')
    order_end   = data.get('order_end')
    deliver_time = (data.get('deliver_time') or '').strip()
    note = (data.get('note') or '').strip()

    if not name or not order_start or not order_end:
        return jsonify({'error': '名称、开始时间、结束时间为必填'}), 400

    try:
        start_dt = _parse_dt(order_start)
        end_dt   = _parse_dt(order_end)
    except ValueError:
        return jsonify({'error': '时间格式有误，应为 YYYY-MM-DD HH:MM'}), 400

    if end_dt <= start_dt:
        return jsonify({'error': '截止时间必须晚于开始时间'}), 400

    s = OrderSession(
        name=name,
        order_start=start_dt,
        order_end=end_dt,
        deliver_time=deliver_time,
        note=note,
    )
    db.session.add(s)
    db.session.commit()
    return jsonify(s.to_dict()), 201


@admin_bp.route('/sessions/<int:sid>', methods=['PUT'])
@admin_required
def update_session(sid):
    s = OrderSession.query.get_or_404(sid)
    data = request.get_json()
    if 'name' in data:
        s.name = data['name'].strip()
    if 'order_start' in data:
        try:
            s.order_start = _parse_dt(data['order_start'])
        except ValueError:
            return jsonify({'error': '开始时间格式有误'}), 400
    if 'order_end' in data:
        try:
            s.order_end = _parse_dt(data['order_end'])
        except ValueError:
            return jsonify({'error': '结束时间格式有误'}), 400
    if 'deliver_time' in data:
        s.deliver_time = data['deliver_time'].strip()
    if 'note' in data:
        s.note = data['note'].strip()
    if 'is_active' in data:
        s.is_active = bool(data['is_active'])
    db.session.commit()
    return jsonify(s.to_dict())


@admin_bp.route('/sessions/<int:sid>', methods=['DELETE'])
@admin_required
def delete_session(sid):
    s = OrderSession.query.get_or_404(sid)
    db.session.delete(s)
    db.session.commit()
    return jsonify({'message': '已删除'})


# ── 收款码管理 ─────────────────────────────────────────
QR_KEYS = {'wechat': 'qr_wechat', 'alipay': 'qr_alipay'}

@admin_bp.route('/qrcode', methods=['GET'])
@admin_required
def get_qrcodes():
    """管理员获取所有收款码（含完整 base64）和收款链接"""
    return jsonify({
        'wechat':     SystemConfig.get('qr_wechat', ''),
        'alipay':     SystemConfig.get('qr_alipay', ''),
        'wechat_url': SystemConfig.get('qr_wechat_url', ''),
        'alipay_url': SystemConfig.get('qr_alipay_url', ''),
    })


@admin_bp.route('/qrcode/<string:qr_type>', methods=['PUT'])
@admin_required
def save_qrcode(qr_type):
    """保存收款码 base64 图片到数据库"""
    if qr_type not in QR_KEYS:
        return jsonify({'error': '类型有误，仅支持 wechat / alipay'}), 400
    data = request.get_json()
    image_data = (data.get('image') or '').strip()
    if not image_data:
        return jsonify({'error': '图片数据不能为空'}), 400
    if not image_data.startswith('data:image/'):
        return jsonify({'error': '图片格式有误'}), 400
    SystemConfig.set(QR_KEYS[qr_type], image_data)
    return jsonify({'message': '保存成功', 'type': qr_type})


@admin_bp.route('/qrcode/<string:qr_type>', methods=['DELETE'])
@admin_required
def delete_qrcode(qr_type):
    """清除收款码"""
    if qr_type not in QR_KEYS:
        return jsonify({'error': '类型有误'}), 400
    SystemConfig.set(QR_KEYS[qr_type], '')
    return jsonify({'message': '已清除'})


URL_KEYS = {'wechat': 'qr_wechat_url', 'alipay': 'qr_alipay_url'}

@admin_bp.route('/qrcode/<string:qr_type>/url', methods=['PUT'])
@admin_required
def save_qrcode_url(qr_type):
    """保存收款链接"""
    if qr_type not in URL_KEYS:
        return jsonify({'error': '类型有误，仅支持 wechat / alipay'}), 400
    data = request.get_json()
    url = (data.get('url') or '').strip()
    SystemConfig.set(URL_KEYS[qr_type], url)
    return jsonify({'message': '保存成功', 'type': qr_type})


# ── 注册用户管理 ────────────────────────────────────────
@admin_bp.route('/users', methods=['GET'])
@admin_required
def get_users():
    """获取所有注册用户列表，支持关键词搜索"""
    from models import User
    q = request.args.get('q', '').strip()
    query = User.query.order_by(User.created_at.desc())
    if q:
        from sqlalchemy import or_
        query = query.filter(
            or_(
                User.name.ilike(f'%{q}%'),
                User.phone.ilike(f'%{q}%'),
                User.class_name.ilike(f'%{q}%'),
            )
        )
    users = query.all()
    result = []
    for u in users:
        order_count = Order.query.filter_by(user_id=u.id).count()
        result.append({
            'id':         u.id,
            'name':       u.name,
            'phone':      u.phone,
            'class_name': u.class_name or '',
            'created_at': u.created_at.strftime('%Y-%m-%d %H:%M:%S'),
            'order_count': order_count,
        })
    return jsonify(result)


@admin_bp.route('/users/<int:uid>', methods=['DELETE'])
@admin_required
def delete_user(uid):
    """删除注册用户（同时删除其所有订单）"""
    from models import User
    user = User.query.get_or_404(uid)
    # 先删关联订单项
    for order in user.orders:
        from models import OrderItem
        OrderItem.query.filter_by(order_id=order.id).delete()
    Order.query.filter_by(user_id=uid).delete()
    db.session.delete(user)
    db.session.commit()
    return jsonify({'message': '已删除'})


# ── 商家联系方式 ────────────────────────────────────────
@admin_bp.route('/contact', methods=['GET'])
@admin_required
def get_contact():
    return jsonify({
        'wechat':  SystemConfig.get('contact_wechat', ''),
        'phone':   SystemConfig.get('contact_phone', ''),
        'remark':  SystemConfig.get('contact_remark', ''),
    })


@admin_bp.route('/contact', methods=['PUT'])
@admin_required
def save_contact():
    data = request.get_json()
    SystemConfig.set('contact_wechat', (data.get('wechat') or '').strip())
    SystemConfig.set('contact_phone',  (data.get('phone')  or '').strip())
    SystemConfig.set('contact_remark', (data.get('remark') or '').strip())
    return jsonify({'message': '保存成功'})
