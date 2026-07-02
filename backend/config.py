import os

# 优先从环境变量读取，生产环境请务必设置 FOOD_SECRET_KEY
SECRET_KEY = os.environ.get('FOOD_SECRET_KEY', 'campus-food-order-secret-2024')
