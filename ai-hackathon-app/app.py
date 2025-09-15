import logging
from flask import Flask, request, jsonify, render_template, redirect, url_for
from flask_sqlalchemy import SQLAlchemy
import os

log_dir = os.path.join(os.path.dirname(__file__), '..', 'logs')
log_file = os.path.abspath(os.path.join(log_dir, 'app.log'))
os.makedirs(log_dir, exist_ok=True)

# Set up logger
logger = logging.getLogger("sre-ai-app")
logger.setLevel(logging.INFO)
file_handler = logging.FileHandler(log_file)
file_handler.setLevel(logging.INFO)
formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
file_handler.setFormatter(formatter)
logger.addHandler(file_handler)





## Removed Loki logger setup and handlers

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///ecommerce.db'
db = SQLAlchemy(app)


class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(80), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)

class Product(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    price = db.Column(db.Float, nullable=False)


class Order(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    product_id = db.Column(db.Integer, db.ForeignKey('product.id'), nullable=False)
    quantity = db.Column(db.Integer, nullable=False)


# USER_INFO model
class USER_INFO(db.Model):
    user_id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    user_name = db.Column(db.String(100), unique=True, nullable=False)
    password = db.Column(db.String(12), nullable=False)
    first_login_ts = db.Column(db.DateTime)
    failed_login_ts = db.Column(db.DateTime)
    failed_login_count = db.Column(db.Integer, default=0)

# Cart model
class Cart(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    product_id = db.Column(db.Integer, db.ForeignKey('product.id'), nullable=False)
    quantity = db.Column(db.Integer, nullable=False, default=1)




# Helper to get cart count for user
def get_cart_count(user_id=1):
    return Cart.query.filter_by(user_id=user_id).count()


# Home page
@app.route('/')
def home():
    cart_count = get_cart_count()
    return render_template('index.html', cart_count=cart_count)

# Login page
@app.route('/login', methods=['GET', 'POST'])
def login():
    error = None
    success = None
    if request.method == 'POST':
        email = request.form.get('user_name', '').strip()
        password = request.form.get('password', '').strip()
        import re
        email_regex = r'^[\w\.-]+@[\w\.-]+\.\w+$'
        if not re.match(email_regex, email):
            error = 'Please enter a valid email address.'
        elif len(password) < 1:
            error = 'Please enter a password.'
            logger.error(f"ERROR: Invalid password attempt for email: {email}")
        else:
            existing_user = USER_INFO.query.filter_by(user_name=email).first()
            if existing_user:
                # User exists, check password
                if existing_user.password == password:
                    # Successful login, redirect to products
                    return redirect(url_for('products_page'))
                else:
                    error = 'invalid username or password'
                    from datetime import datetime
                    existing_user.failed_login_count = (existing_user.failed_login_count or 0) + 1
                    existing_user.failed_login_ts = datetime.now()
                    db.session.commit()
                    logger.error(f"invalid login attempt for email id: {email}")
            else:
                from datetime import datetime
                new_user = USER_INFO(
                    user_name=email,
                    password=password,
                    first_login_ts=datetime.now(),
                    failed_login_ts=None,
                    failed_login_count=0
                )
                db.session.add(new_user)
                db.session.commit()
                success = 'User created successfully! Please login.'
    return render_template('login.html', error=error, success=success)


# Products page with Add to Cart
def save_product_to_cart(product_id, user_id=1, quantity=1):
    cart_item = Cart(user_id=user_id, product_id=product_id, quantity=quantity)
    db.session.add(cart_item)
    db.session.commit()


@app.route('/products', methods=['GET', 'POST'])
def products_page():
    products = Product.query.all()
    cart_count = get_cart_count()
    image_urls = [
        "https://images.unsplash.com/photo-1506744038136-46273834b3fb?auto=format&fit=crop&w=120&q=80",
        "https://images.unsplash.com/photo-1465101046530-73398c7f28ca?auto=format&fit=crop&w=120&q=80",
        "https://images.unsplash.com/photo-1515165562835-cf7747c1bc6b?auto=format&fit=crop&w=120&q=80",
        "https://images.unsplash.com/photo-1519125323398-675f0ddb6308?auto=format&fit=crop&w=120&q=80",
        "https://images.unsplash.com/photo-1526178613658-3f1622045544?auto=format&fit=crop&w=120&q=80"
    ]
    for i, p in enumerate(products):
        p.image_url = image_urls[i % len(image_urls)]

    if request.method == 'POST':
        product_id = int(request.form['product_id'])
        user_id = int(request.form.get('user_id', 1))  # Default user_id=1 for demo
        save_product_to_cart(product_id, user_id)
        cart_count = get_cart_count()
        return render_template('products.html', products=products, message='Added to cart!', cart_count=cart_count)

    return render_template('products.html', products=products, cart_count=cart_count)
# Cart page
@app.route('/cart')
def cart_page():
    user_id = 1  # demo user
    cart_items = Cart.query.filter_by(user_id=user_id).all()
    products = {p.id: p for p in Product.query.all()}
    cart_products = []
    for item in cart_items:
        prod = products.get(item.product_id)
        if prod:
            cart_products.append({
                'name': prod.name,
                'price': prod.price,
                'quantity': item.quantity,
                'image_url': prod.image_url if hasattr(prod, 'image_url') else '',
            })
    cart_count = len(cart_items)
    return render_template('cart.html', cart_products=cart_products, cart_count=cart_count)

# Users page
@app.route('/users')
def users_page():
    users = USER_INFO.query.all()
    return render_template('users.html', users=users)

# Orders page
@app.route('/orders')
def orders_page():
    orders = Order.query.all()
    return render_template('orders.html', orders=orders)

# API endpoints
@app.route('/api/users', methods=['POST'])
def create_user():
    data = request.json
    user = User(name=data['name'], email=data['email'])
    db.session.add(user)
    db.session.commit()
    return jsonify({'id': user.id, 'name': user.name, 'email': user.email})


@app.route('/api/products', methods=['POST'])
def create_product():
    data = request.json
    product = Product(name=data['name'], price=data['price'])
    db.session.add(product)
    db.session.commit()
    return jsonify({'id': product.id, 'name': product.name, 'price': product.price})


@app.route('/api/orders', methods=['POST'])
def create_order():
    data = request.json
    order = Order(user_id=data['user_id'], product_id=data['product_id'], quantity=data['quantity'])
    db.session.add(order)
    db.session.commit()
    return jsonify({'id': order.id, 'user_id': order.user_id, 'product_id': order.product_id, 'quantity': order.quantity})


@app.route('/api/users', methods=['GET'])
def get_users():
    users = User.query.all()
    return jsonify([{'id': u.id, 'name': u.name, 'email': u.email} for u in users])


@app.route('/api/products', methods=['GET'])
def get_products():
    products = Product.query.all()
    return jsonify([{'id': p.id, 'name': p.name, 'price': p.price} for p in products])


@app.route('/api/orders', methods=['GET'])
def get_orders():
    orders = Order.query.all()
    return jsonify([{'id': o.id, 'user_id': o.user_id, 'product_id': o.product_id, 'quantity': o.quantity} for o in orders])

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(debug=True)
