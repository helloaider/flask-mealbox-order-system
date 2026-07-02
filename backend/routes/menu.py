from flask import Blueprint, jsonify
from models import MenuItem, ComboType, PickupPoint, OrderSession, SystemConfig
from datetime import datetime

menu_bp = Blueprint('menu', __name__)


@menu_bp.route('', methods=['GET'])
def get_menu():
    items = MenuItem.query.filter_by(is_available=True).all()
    return jsonify([i.to_dict() for i in items])


@menu_bp.route('/combos', methods=['GET'])
def get_combos():
    combos = ComboType.query.all()
    return jsonify([c.to_dict() for c in combos])


@menu_bp.route('/pickup', methods=['GET'])
def get_pickup():
    """公开接口：获取所有启用的取餐点"""
    points = PickupPoint.query.filter_by(is_active=True).all()
    return jsonify([p.to_dict() for p in points])


@menu_bp.route('/session', methods=['GET'])
def get_current_session():
    """公开接口：返回当前及即将开放的餐次列表"""
    now = datetime.now()

    # 当前正在开放的餐次（可能多个）
    open_sessions = OrderSession.query.filter(
        OrderSession.is_active == True,
        OrderSession.order_start <= now,
        OrderSession.order_end >= now,
    ).order_by(OrderSession.order_start.asc()).all()

    # 即将开放的餐次（最近 3 个，供用户预览）
    upcoming_sessions = OrderSession.query.filter(
        OrderSession.is_active == True,
        OrderSession.order_start > now,
    ).order_by(OrderSession.order_start.asc()).limit(3).all()

    is_open = len(open_sessions) > 0

    # 兼容旧字段：session 取第一个开放餐次（横幅展示用）
    first_session = open_sessions[0] if open_sessions else (
        upcoming_sessions[0] if upcoming_sessions else None
    )

    return jsonify({
        'is_open': is_open,
        'session': first_session.to_dict() if first_session else None,
        'open_sessions': [s.to_dict() for s in open_sessions],
        'upcoming_sessions': [s.to_dict() for s in upcoming_sessions],
    })


@menu_bp.route('/qrcode', methods=['GET'])
def get_qrcode_public():
    """公开接口：获取收款码（用户结算时展示，无需登录）"""
    return jsonify({
        'wechat':     SystemConfig.get('qr_wechat', ''),
        'alipay':     SystemConfig.get('qr_alipay', ''),
        'wechat_url': SystemConfig.get('qr_wechat_url', ''),
        'alipay_url': SystemConfig.get('qr_alipay_url', ''),
    })


@menu_bp.route('/contact', methods=['GET'])
def get_contact_public():
    """公开接口：获取商家联系方式（无需登录）"""
    return jsonify({
        'wechat':  SystemConfig.get('contact_wechat', ''),
        'phone':   SystemConfig.get('contact_phone', ''),
        'remark':  SystemConfig.get('contact_remark', ''),
    })
