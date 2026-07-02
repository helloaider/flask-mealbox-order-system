"""初始化数据：管理员账号 + 菜品 + 套餐类型"""
from werkzeug.security import generate_password_hash
from models import db, Admin, MenuItem, ComboType


def seed_data():
    # 管理员
    if not Admin.query.filter_by(username='admin').first():
        admin = Admin(username='admin', password_hash=generate_password_hash('admin123'))
        db.session.add(admin)

    # 荤菜
    meats = [
        ('红烧肉', '🥩', 7.0),
        ('可乐鸡翅', '🍗', 8.0),
        ('鱼香肉丝', '🍖', 7.0),
        ('宫保鸡丁', '🍗', 8.0),
        ('糖醋排骨', '🥩', 8.0),
        ('回锅肉', '🍖', 7.0),
    ]
    for name, emoji, price in meats:
        if not MenuItem.query.filter_by(name=name).first():
            db.session.add(MenuItem(name=name, category='荤', price=price, emoji=emoji))

    # 素菜
    vegs = [
        ('炒青菜', '🥬', 3.0),
        ('土豆丝', '🥔', 4.0),
        ('番茄炒蛋', '🍅', 4.0),
        ('豆腐脑', '🫘', 3.0),
        ('清炒藕片', '🌿', 4.0),
        ('木耳炒蛋', '🍄', 4.0),
    ]
    for name, emoji, price in vegs:
        if not MenuItem.query.filter_by(name=name).first():
            db.session.add(MenuItem(name=name, category='素', price=price, emoji=emoji))

    # 主食（米饭：每单自动附带1份，价格2元，计入套餐总价）
    if not MenuItem.query.filter_by(name='米饭').first():
        db.session.add(MenuItem(name='米饭', category='主食', price=2.0, emoji='🍚'))

    # 套餐
    # 价格规律：price = 10 + 荤数×2 + 素数×1（含米饭2元，底座8元）
    # 验证：1荤1素=13 ✓  2荤2素=16 ✓  0荤1素=11 ✓
    combos = [
        # 纯素套餐
        ('一素套餐',   0, 1, 11.0, '0荤+1素+饭，简单清爽'),
        ('两素套餐',   0, 2, 12.0, '0荤+2素+饭，清淡健康'),
        ('三素套餐',   0, 3, 13.0, '0荤+3素+饭，全素丰富'),
        # 一荤系列
        ('一荤一素套餐', 1, 1, 13.0, '1荤+1素+饭，经济实惠'),
        ('一荤两素套餐', 1, 2, 14.0, '1荤+2素+饭，荤素搭配'),
        ('一荤三素套餐', 1, 3, 15.0, '1荤+3素+饭，蔬菜丰富'),
        # 两荤系列
        ('两荤一素套餐', 2, 1, 15.0, '2荤+1素+饭，营养均衡'),
        ('两荤两素套餐', 2, 2, 16.0, '2荤+2素+饭，丰盛美味'),
        ('两荤三素套餐', 2, 3, 17.0, '2荤+3素+饭，超值丰盛'),
        # 三荤系列
        ('三荤一素套餐', 3, 1, 17.0, '3荤+1素+饭，大荤重口'),
        ('三荤两素套餐', 3, 2, 18.0, '3荤+2素+饭，豪华套餐'),
        ('三荤三素套餐', 3, 3, 19.0, '3荤+3素+饭，至尊满足'),
    ]
    for name, meat, veg, price, desc in combos:
        existing = ComboType.query.filter_by(name=name).first()
        if not existing:
            db.session.add(ComboType(name=name, meat_count=meat, veg_count=veg, price=price, description=desc))
        else:
            # 更新价格（确保已有数据也同步正确价格）
            existing.price = price
            existing.meat_count = meat
            existing.veg_count = veg
            existing.description = desc

    db.session.commit()
    print('✅ 初始数据已写入')
