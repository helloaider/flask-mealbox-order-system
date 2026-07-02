import random
from flask import Blueprint, request, jsonify
from models import db, Order, OrderItem, MenuItem, ComboType, OrderSession, PickupPoint
from sqlalchemy.orm import joinedload
from utils import student_required
from datetime import datetime

orders_bp = Blueprint('orders', __name__)

RICE_NAME = '米饭'   # 自动附带的主食名称


def get_open_session(session_id=None):
    """返回指定的或当前开放的餐次。
    允许预约：若用户指定了一个 upcoming（未来）餐次，也视为合法。
    """
    now = datetime.now()
    if session_id:
        s = OrderSession.query.filter_by(id=int(session_id), is_active=True).first()
        if not s:
            return None
        # 当前开放 或 尚未开始（预约）均允许；已结束的不允许
        if s.order_end < now:
            return None
        return s
    # 未指定餐次：自动取当前开放的第一个
    return OrderSession.query.filter(
        OrderSession.is_active == True,
        OrderSession.order_start <= now,
        OrderSession.order_end >= now,
    ).first()


def get_rice():
    """返回米饭 MenuItem，未找到返回 None"""
    return MenuItem.query.filter_by(name=RICE_NAME, is_available=True).first()


def append_rice(order_id, rice):
    """给订单追加一份米饭 OrderItem"""
    db.session.add(OrderItem(
        order_id=order_id,
        menu_item_id=rice.id,
        quantity=1,
        price=rice.price,
    ))


@orders_bp.route('', methods=['POST'])
@student_required
def create_order(current_user):
    data = request.get_json()
    order_type = data.get('order_type')  # combo / custom
    note    = data.get('note', '')
    address = (data.get('address') or '').strip()
    payment_note    = (data.get('payment_note')    or '').strip()
    payment_channel = (data.get('payment_channel') or 'wechat').strip()
    if payment_channel not in ('wechat', 'alipay', 'cash'):
        payment_channel = 'wechat'

    # 餐次：优先用用户选择的，否则自动取当前开放的
    chosen_session_id = data.get('session_id')
    session = get_open_session(chosen_session_id)
    if not session:
        if chosen_session_id:
            return jsonify({'error': '所选餐次已结束或不存在，请重新选择'}), 400
        return jsonify({'error': '当前没有可下单的餐次，请选择一个即将开放的餐次或等待管理员开放餐次'}), 403

    # 取餐点（可选，优先用 pickup_point_id；兼容旧的纯文本 address）
    pickup_point_id = data.get('pickup_point_id')
    pickup_point = None
    if pickup_point_id:
        pickup_point = PickupPoint.query.filter_by(id=int(pickup_point_id), is_active=True).first()
        if not pickup_point:
            return jsonify({'error': '所选取餐点不存在或已关闭'}), 400
        address = pickup_point.name + ' - ' + pickup_point.location
    elif not address:
        return jsonify({'error': '请选择取餐点或填写送餐地址'}), 400

    # ── 防重复下单：同用户同餐次已存在未完成订单则拒绝 ──
    if session:
        existing = Order.query.filter(
            Order.user_id == current_user.id,
            Order.session_id == session.id,
            Order.status.notin_(['delivered']),
        ).first()
        if existing:
            return jsonify({'error': f'您在本餐次已有订单（#{existing.id}），请勿重复下单'}), 400

    rice = get_rice()   # 米饭菜品，可能为 None（未配置时不强制）

    if order_type == 'combo':
        combo_type_id = data.get('combo_type_id')
        combo = ComboType.query.get(combo_type_id)
        if not combo:
            return jsonify({'error': '套餐不存在'}), 400

        meats = MenuItem.query.filter_by(category='荤', is_available=True).all()
        vegs  = MenuItem.query.filter_by(category='素', is_available=True).all()
        if len(meats) < combo.meat_count or len(vegs) < combo.veg_count:
            return jsonify({'error': '当前可用菜品不足，无法生成套餐'}), 400

        chosen = random.sample(meats, combo.meat_count) + random.sample(vegs, combo.veg_count)
        # 套餐价已含米饭，total_price 直接用套餐价
        order = Order(
            user_id=current_user.id, session_id=session.id,
            pickup_point_id=pickup_point.id if pickup_point else None,
            order_type='combo', combo_type_id=combo.id,
            total_price=combo.price, note=note, address=address,
            status='unpaid', payment_note=payment_note,
            payment_channel=payment_channel,
        )
        db.session.add(order)
        db.session.flush()
        for mi in chosen:
            db.session.add(OrderItem(order_id=order.id, menu_item_id=mi.id, quantity=1, price=mi.price))
        if rice:
            append_rice(order.id, rice)
        db.session.commit()
        return jsonify(order.to_dict()), 201

    elif order_type == 'custom':
        items_data = data.get('items', [])
        if not items_data:
            return jsonify({'error': '请至少选择一道菜'}), 400

        order_items = []
        meat_count = 0
        veg_count  = 0
        for item_d in items_data:
            mi = MenuItem.query.get(item_d.get('menu_item_id'))
            if not mi or not mi.is_available:
                return jsonify({'error': '菜品不可用'}), 400
            if mi.category == '主食':   # 前端不应提交主食，忽略
                continue
            qty = int(item_d.get('quantity', 1))
            if qty < 1:
                continue
            if mi.category == '荤':
                meat_count += qty
            elif mi.category == '素':
                veg_count += qty
            order_items.append((mi, qty))

        if not order_items:
            return jsonify({'error': '请至少选择一道菜'}), 400

        # 按套餐公式计价：10 + 荤数×2 + 素数×1（含米饭2元）
        total = round(10.0 + meat_count * 2.0 + veg_count * 1.0, 2)

        order = Order(
            user_id=current_user.id, session_id=session.id,
            pickup_point_id=pickup_point.id if pickup_point else None,
            order_type='custom', total_price=total,
            note=note, address=address,
            status='unpaid', payment_note=payment_note,
            payment_channel=payment_channel,
        )
        db.session.add(order)
        db.session.flush()
        for mi, qty in order_items:
            db.session.add(OrderItem(order_id=order.id, menu_item_id=mi.id, quantity=qty, price=0.0))
        if rice:
            append_rice(order.id, rice)
        db.session.commit()
        return jsonify(order.to_dict()), 201

    else:
        return jsonify({'error': '无效的 order_type'}), 400


@orders_bp.route('/my', methods=['GET'])
@student_required
def my_orders(current_user):
    orders = (
        Order.query
        .filter_by(user_id=current_user.id)
        .options(
            joinedload(Order.items).joinedload(OrderItem.menu_item),
            joinedload(Order.session),
            joinedload(Order.pickup_point),
        )
        .order_by(Order.created_at.desc())
        .all()
    )
    return jsonify([o.to_dict() for o in orders])
