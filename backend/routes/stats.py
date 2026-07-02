"""
统计分析 API
GET /api/admin/stats?range=today|week|month|all&session_id=<id>
"""
from flask import Blueprint, request, jsonify
from models import db, Order, OrderItem, MenuItem, ComboType, PickupPoint, OrderSession
from utils import admin_required
from sqlalchemy import func, case
from datetime import datetime, timedelta

stats_bp = Blueprint('stats', __name__)


def _date_range(range_type: str):
    """返回 (start_dt, end_dt) 或 (None, None) 表示全部"""
    now = datetime.now()
    if range_type == 'today':
        start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        end   = now.replace(hour=23, minute=59, second=59, microsecond=999999)
        return start, end
    if range_type == 'week':
        start = (now - timedelta(days=now.weekday())).replace(hour=0, minute=0, second=0, microsecond=0)
        end   = now
        return start, end
    if range_type == 'month':
        start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        end   = now
        return start, end
    return None, None   # 'all'


@stats_bp.route('', methods=['GET'])
@admin_required
def get_stats():
    range_type = request.args.get('range', 'all')
    session_id = request.args.get('session_id', type=int)
    start_dt, end_dt = _date_range(range_type)

    # ── 基础查询集 ──────────────────────────────────────────
    q = Order.query
    if start_dt:
        q = q.filter(Order.created_at >= start_dt, Order.created_at <= end_dt)
    if session_id:
        q = q.filter(Order.session_id == session_id)

    orders = q.all()
    total  = len(orders)

    if total == 0:
        return jsonify({
            'summary': {
                'total_orders':     0,
                'delivered_orders': 0,
                'total_revenue':    0,
                'pending_orders':   0,
                'avg_price':        0,
            },
            'status_dist':    [],
            'revenue_trend':  [],
            'top_dishes':     [],
            'combo_dist':     [],
            'pickup_dist':    [],
            'order_type_dist': [],
            'channel_dist':   [],
            'hourly_dist':    [],
            'session_summary': [],
        })

    # ── 汇总指标 ───────────────────────────────────────────
    delivered = [o for o in orders if o.status == 'delivered']
    pending   = [o for o in orders if o.status in ('unpaid', 'pending', 'preparing', 'delivering')]
    revenue   = sum(o.total_price for o in orders)
    avg_price = round(revenue / total, 2)

    summary = {
        'total_orders':     total,
        'delivered_orders': len(delivered),
        'total_revenue':    round(revenue, 2),
        'pending_orders':   len(pending),
        'avg_price':        avg_price,
    }

    # ── 订单状态分布 ─────────────────────────────────────────
    STATUS_LABEL = {
        'unpaid':     '待收款',
        'pending':    '待制作',
        'preparing':  '制作中',
        'delivering': '配送中',
        'delivered':  '已送达',
    }
    status_count = {}
    for o in orders:
        status_count[o.status] = status_count.get(o.status, 0) + 1
    status_dist = [
        {'status': k, 'label': STATUS_LABEL.get(k, k), 'count': v}
        for k, v in status_count.items()
    ]

    # ── 收入趋势（按日/小时） ────────────────────────────────
    if range_type in ('today',):
        # 按小时分组
        trend_map = {}
        for o in orders:
            key = o.created_at.strftime('%H:00')
            trend_map[key] = trend_map.get(key, 0) + o.total_price
        # 补全 0-23 小时
        revenue_trend = [
            {'label': f'{h:02d}:00', 'revenue': round(trend_map.get(f'{h:02d}:00', 0), 2),
             'count': sum(1 for o in orders if o.created_at.hour == h)}
            for h in range(24)
        ]
    elif range_type == 'week':
        WEEK_CN = ['周一', '周二', '周三', '周四', '周五', '周六', '周日']
        trend_map = {}
        for o in orders:
            key = o.created_at.strftime('%Y-%m-%d')
            trend_map[key] = trend_map.get(key, {'revenue': 0, 'count': 0})
            trend_map[key]['revenue'] += o.total_price
            trend_map[key]['count']   += 1
        now = datetime.now()
        week_start = (now - timedelta(days=now.weekday())).replace(hour=0, minute=0, second=0, microsecond=0)
        revenue_trend = []
        for i in range(7):
            day = week_start + timedelta(days=i)
            key = day.strftime('%Y-%m-%d')
            d   = trend_map.get(key, {'revenue': 0, 'count': 0})
            revenue_trend.append({
                'label':   WEEK_CN[i],
                'revenue': round(d['revenue'], 2),
                'count':   d['count'],
            })
    elif range_type == 'month':
        trend_map = {}
        for o in orders:
            key = o.created_at.strftime('%m/%d')
            trend_map[key] = trend_map.get(key, {'revenue': 0, 'count': 0})
            trend_map[key]['revenue'] += o.total_price
            trend_map[key]['count']   += 1
        now = datetime.now()
        revenue_trend = []
        for i in range(now.day):
            day = now.replace(day=1) + timedelta(days=i)
            key = day.strftime('%m/%d')
            d   = trend_map.get(key, {'revenue': 0, 'count': 0})
            revenue_trend.append({
                'label':   key,
                'revenue': round(d['revenue'], 2),
                'count':   d['count'],
            })
    else:
        # 全部：按日期分组，最近30天
        trend_map = {}
        for o in orders:
            key = o.created_at.strftime('%Y-%m-%d')
            trend_map[key] = trend_map.get(key, {'revenue': 0, 'count': 0})
            trend_map[key]['revenue'] += o.total_price
            trend_map[key]['count']   += 1
        sorted_days = sorted(trend_map.keys())
        revenue_trend = [
            {'label': k, 'revenue': round(trend_map[k]['revenue'], 2), 'count': trend_map[k]['count']}
            for k in sorted_days
        ]

    # ── 热门菜品 Top10 ──────────────────────────────────────
    order_ids = [o.id for o in orders]
    dish_count = {}
    if order_ids:
        items = OrderItem.query.filter(OrderItem.order_id.in_(order_ids)).all()
        # 一次性加载所有涉及的 MenuItem，避免 N+1
        mi_ids = list({item.menu_item_id for item in items})
        mi_map = {m.id: m for m in MenuItem.query.filter(MenuItem.id.in_(mi_ids)).all()}
        for item in items:
            mi = mi_map.get(item.menu_item_id)
            if mi and mi.name != '米饭':
                key = (mi.name, mi.emoji, mi.category)
                dish_count[key] = dish_count.get(key, 0) + item.quantity

    top_dishes = sorted(
        [{'name': k[0], 'emoji': k[1], 'category': k[2], 'count': v}
         for k, v in dish_count.items()],
        key=lambda x: -x['count']
    )[:10]

    # ── 套餐销售分布 ─────────────────────────────────────────
    # 一次性加载所有涉及的 ComboType
    ct_ids = list({o.combo_type_id for o in orders if o.order_type == 'combo' and o.combo_type_id})
    ct_map = {c.id: c for c in ComboType.query.filter(ComboType.id.in_(ct_ids)).all()} if ct_ids else {}
    combo_count = {}
    for o in orders:
        if o.order_type == 'combo' and o.combo_type_id:
            ct = ct_map.get(o.combo_type_id)
            name = ct.name if ct else f'套餐#{o.combo_type_id}'
            combo_count[name] = combo_count.get(name, 0) + 1
    combo_dist = [{'name': k, 'count': v} for k, v in combo_count.items()]
    combo_dist.sort(key=lambda x: -x['count'])

    # ── 取餐点分布 ──────────────────────────────────────────
    pp_ids = list({o.pickup_point_id for o in orders if o.pickup_point_id})
    pp_map = {p.id: p for p in PickupPoint.query.filter(PickupPoint.id.in_(pp_ids)).all()} if pp_ids else {}
    pickup_count = {}
    for o in orders:
        if o.pickup_point_id:
            pp = pp_map.get(o.pickup_point_id)
            name = pp.name if pp else f'取餐点#{o.pickup_point_id}'
        else:
            name = o.address or '自定义地址'
        pickup_count[name] = pickup_count.get(name, 0) + 1
    pickup_dist = sorted(
        [{'name': k, 'count': v} for k, v in pickup_count.items()],
        key=lambda x: -x['count']
    )

    # ── 套餐 vs 自选分布 ─────────────────────────────────────
    combo_n  = sum(1 for o in orders if o.order_type == 'combo')
    custom_n = sum(1 for o in orders if o.order_type == 'custom')
    order_type_dist = [
        {'type': 'combo',  'label': '套餐',  'count': combo_n},
        {'type': 'custom', 'label': '自选餐', 'count': custom_n},
    ]

    # ── 支付渠道分布 ──────────────────────────────────────────
    channel_count = {}
    CHANNEL_LABEL = {'wechat': '微信支付', 'alipay': '支付宝', 'cash': '现金'}
    for o in orders:
        ch = o.payment_channel or 'wechat'
        channel_count[ch] = channel_count.get(ch, 0) + 1
    channel_dist = [
        {'channel': k, 'label': CHANNEL_LABEL.get(k, k), 'count': v}
        for k, v in channel_count.items()
    ]

    # ── 下单时段分布（0-23点） ──────────────────────────────
    hourly = [0] * 24
    for o in orders:
        hourly[o.created_at.hour] += 1
    hourly_dist = [{'hour': h, 'label': f'{h}时', 'count': hourly[h]} for h in range(24)]

    # ── 各餐次汇总（仅全部/无餐次筛选时） ─────────────────────
    session_summary = []
    if not session_id:
        sess_map = {}
        for o in orders:
            sid = o.session_id
            sname = o.session.name if o.session else '无餐次'
            if sid not in sess_map:
                sess_map[sid] = {'session_id': sid, 'name': sname, 'count': 0, 'revenue': 0.0}
            sess_map[sid]['count']   += 1
            sess_map[sid]['revenue'] += o.total_price
        session_summary = sorted(
            [{'session_id': v['session_id'], 'name': v['name'],
              'count': v['count'], 'revenue': round(v['revenue'], 2)}
             for v in sess_map.values()],
            key=lambda x: -(x['count'])
        )

    return jsonify({
        'summary':         summary,
        'status_dist':     status_dist,
        'revenue_trend':   revenue_trend,
        'top_dishes':      top_dishes,
        'combo_dist':      combo_dist,
        'pickup_dist':     pickup_dist,
        'order_type_dist': order_type_dist,
        'channel_dist':    channel_dist,
        'hourly_dist':     hourly_dist,
        'session_summary': session_summary,
    })
