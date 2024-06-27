from flask import Flask, render_template, redirect, url_for, flash, request, abort, jsonify
from flask_bootstrap import Bootstrap
from flask_ckeditor import CKEditor
from datetime import date
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.orm import relationship
from sqlalchemy import exc, ForeignKey
from flask_login import UserMixin, login_user, LoginManager, login_required, current_user, logout_user
from forms import CreateItem, CreateUser, LogInUser, ReviewForm, AddAddress
from flask_gravatar import Gravatar
from functools import wraps
from PIL import Image
import stripe
from stripe import error
import smtplib
import json
import os

stripe.api_key = os.environ["stripe_api_key"]
MY_DOMAIN = os.environ["MY_DOMAIN"]
MY_EMAIL = os.environ["MY_EMAIL"]
PASSWORD = os.environ["PASSWORD"]
app = Flask(__name__, static_url_path='/static')
app.config['SECRET_KEY'] = os.environ["SECRET_KEY"]
ckeditor = CKEditor(app)
Bootstrap(app)

# CONNECT TO DB
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///store_db.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

login_manager = LoginManager()
login_manager.init_app(app)

# gravatar = Gravatar(app, size=100, rating='g', default='retro', force_default=False, force_lower=False, use_ssl=False,
#                     base_url=None)


# CONFIGURE TABLES

class Item(db.Model):
    __tablename__ = "item"
    id = db.Column(db.Integer, primary_key=True)
    item_code = db.Column(db.String(250), unique=True, nullable=False)
    item_name = db.Column(db.String(250), unique=True, nullable=False)
    description = db.Column(db.Text, nullable=False)
    img_icon = db.Column(db.String(500), nullable=False)
    img_lrg = db.Column(db.String(500), nullable=False)
    price = db.Column(db.Integer, nullable=False)
    price_api = db.Column(db.Integer, nullable=False)
    category = db.Column(db.String(100))
    views = db.Column(db.Integer, nullable=False)
    sold = db.Column(db.Integer, nullable=False)
    reviews = relationship("Review", back_populates="item_review")
    item_actions = relationship("ItemActions", back_populates="item_requested")
    order_history = relationship("OrderHistory", back_populates="item_requested")


class User(db.Model, UserMixin):
    __tablename__ = "users"
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(100), unique=True)
    password = db.Column(db.String(100), nullable=False)
    name = db.Column(db.String(100), nullable=False)
    surname = db.Column(db.String(100), nullable=False)
    date_of_birth = db.Column(db.String(100), nullable=False)
    member_since = db.Column(db.String(100), nullable=False)
    reviews = relationship("Review", back_populates="review_author")
    address = relationship("Address", back_populates="resident")
    item_actions = relationship("ItemActions", back_populates="creator")
    order_history = relationship("OrderHistory", back_populates="creator")


class Review(db.Model):
    __tablename__ = "reviews"
    id = db.Column(db.Integer, primary_key=True)
    text = db.Column(db.Text, nullable=False)
    rating = db.Column(db.Integer, nullable=False)
    review_author = relationship("User", back_populates="reviews")
    author_id = db.Column(db.Integer, db.ForeignKey("users.id"))
    item_review = relationship("Item", back_populates="reviews")
    item_id = db.Column(db.Integer, db.ForeignKey("item.id"))


class Address(db.Model):
    __tablename__ = "address"
    id = db.Column(db.Integer, primary_key=True)
    country = db.Column(db.String(100), nullable=False)
    region = db.Column(db.String(100), nullable=False)
    city = db.Column(db.String(100), nullable=False)
    street = db.Column(db.String(100), nullable=False)
    street_number = db.Column(db.String(100), nullable=False)
    address_type = db.Column(db.String(100), nullable=False)
    resident = relationship("User", back_populates="address")
    resident_id = db.Column(db.Integer, db.ForeignKey("users.id"))
    order_history = relationship("OrderHistory", back_populates="address")


class ItemActions(db.Model):
    __tablename__ = "item_actions"
    id = db.Column(db.Integer, primary_key=True)
    wishlist = db.Column(db.Boolean, nullable=False)
    ordered = db.Column(db.Integer, nullable=False)
    in_cart = db.Column(db.Boolean, nullable=False)
    cart_quantity = db.Column(db.Integer, nullable=False)
    creator = relationship("User", back_populates="item_actions")
    creator_id = db.Column(db.Integer, db.ForeignKey("users.id"))
    item_requested = relationship("Item", back_populates="item_actions")
    item_requested_id = db.Column(db.Integer, db.ForeignKey("item.id"))


class OrderHistory(db.Model):
    __tablename__ = "order_history"
    id = db.Column(db.Integer, primary_key=True)
    order_number = db.Column(db.String(100), nullable=False)
    order_date = db.Column(db.String(100), nullable=False)
    item_requested = relationship("Item", back_populates="order_history")
    item_requested_id = db.Column(db.Integer, db.ForeignKey("item.id"))
    quantity_ordered = db.Column(db.Integer, nullable=False)
    creator = relationship("User", back_populates="order_history")
    creator_id = db.Column(db.Integer, db.ForeignKey("users.id"))
    address = relationship("Address", back_populates="order_history")
    address_id = db.Column(db.Integer, db.ForeignKey("address.id"))


with app.app_context():
    db.create_all()


def resize_image(imagefile, item_code):
    filename = secure_filename(imagefile.data.filename)
    file_save = "static/img/" + item_code
    img_ext = "." + filename.split(".")[1]
    imagefile.data.save(file_save + img_ext)
    image = Image.open(file_save + img_ext)
    image.thumbnail((500, 500), Image.ANTIALIAS)
    image.save(file_save + "_lrg" + img_ext)
    image = Image.open(file_save + img_ext)
    image.thumbnail((200, 200), Image.ANTIALIAS)
    image.save(file_save + "_icon" + img_ext)
    file_save = file_save.replace("static/", "")
    return file_save + "_lrg" + img_ext, file_save + "_icon" + img_ext


def find_ratings(items):
    ratings = []
    if type(items) != list:
        item = items
        items = [item]
    for requested_item in items:
        sum_rating = 0
        comments = Review.query.filter_by(item_review=requested_item).all()
        if len(comments) > 0:
            for comment in comments:
                sum_rating += comment.rating
            rating_avg = sum_rating / len(comments)
            rounded_rating = round(sum_rating / len(comments))
            ratings.append({"rating_avg": rating_avg, "rounded_rating": rounded_rating, "reviews": len(comments)})
        else:
            ratings.append({"rating_avg": 0, "rounded_rating": 0, "reviews": 0})
    return ratings


@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))


def admin_only(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if current_user.id != 1:
            return abort(403, description="Unauthorised Access\n\nCheck your Credentials")
        return f(*args, **kwargs)

    return decorated_function


@app.route('/')
def get_all_posts():
    items = Item.query.all()
    item_rating = find_ratings(items)
    return render_template("index.html", all_items=items, item_rating=item_rating)


@app.route('/register', methods=["GET", "POST"])
def register():
    form = CreateUser()
    form.validate()
    if request.method == "POST":
        with app.app_context():
            try:
                user_to_be_added = User(email=form.email.data,
                                        password=generate_password_hash(form.password.data),
                                        name=form.name.data,
                                        surname=form.surname.data,
                                        date_of_birth=form.date_of_birth.data.strftime("%d/%m/%Y"),
                                        member_since=date.today().strftime("%d/%m/%Y"))
                db.session.add(user_to_be_added)
                db.session.commit()
                login_user(user_to_be_added)
                return redirect(url_for("get_all_posts"))
            except exc.IntegrityError:
                db.session.rollback()
                flash("There was a problem registering, make sure you have all the fields filled correctly or that "
                      "you haven't already registered with this email")
                return redirect(url_for("login"))
    return render_template("register.html", form=form)


@app.route('/login', methods=['GET', 'POST'])
def login():
    form = LogInUser()
    form.validate()
    if request.method == "POST":
        logging_in_user = User.query.filter_by(email=form.email.data).first()
        login_password = form.password.data
        if logging_in_user:
            if check_password_hash(logging_in_user.password, login_password):
                login_user(logging_in_user)
                return redirect(url_for("get_all_posts"))
            else:
                flash("Incorrect Password")
                return render_template("login.html", form=form)
        else:
            flash("This email does not exist, please try again")
    return render_template("login.html", form=form)


@app.route('/logout')
def logout():
    logout_user()
    return redirect(url_for('get_all_posts'))


@app.route("/item/<int:item_id>", methods=['GET', 'POST'])
def show_item(item_id):
    requested_item = Item.query.get(item_id)
    comments = Review.query.filter_by(item_review=requested_item).all()
    item_rating = find_ratings(requested_item)
    review_form = ReviewForm()
    review_form.validate()
    if request.method == "POST":
        if current_user.is_authenticated:
            review_text = review_form.review.data
            review_text = review_text.replace("<p>", "")
            review_text = review_text.replace("</p>", "")
            comment_to_be_added = Review(text=review_text,
                                         rating=review_form.rating.data,
                                         review_author=current_user,
                                         item_review=requested_item)
            db.session.add(comment_to_be_added)
            db.session.commit()
            comments = Review.query.filter_by(item_review=requested_item).all()
            item_rating = find_ratings(requested_item)
            return render_template("post.html", item=requested_item, form=review_form, comments=comments,
                                   item_rating=item_rating)
        else:
            flash("You have to login first.")
            return redirect(url_for("login"))
    return render_template("post.html", item=requested_item, form=review_form, comments=comments,
                           item_rating=item_rating)


@app.route("/about")
def about():
    return render_template("about.html")


@app.route("/contact")
def contact():
    return render_template("contact.html")


@app.route("/cart/<int:item_id>", methods=["GET", "POST"])
@login_required
def shopping_cart(item_id):
    if item_id:
        requested_item = Item.query.get(item_id)
        check_new = ItemActions.query.filter_by(creator=current_user, item_requested=requested_item).all()
        if not check_new:
            item_to_cart = ItemActions(wishlist=False,
                                       ordered=0,
                                       in_cart=True,
                                       cart_quantity=1,
                                       creator=current_user,
                                       item_requested=requested_item)
            db.session.add(item_to_cart)
            db.session.commit()
        else:
            item_action = ItemActions.query.get(check_new[0].id)
            item_action.in_cart = True
            item_action.cart_quantity += 1
            db.session.commit()
    cart_items = ItemActions.query.filter_by(creator=current_user, in_cart=True).all()
    requested_items = []
    total_price = 0
    for item in cart_items:
        requested_items.append({"item": Item.query.get(item.item_requested_id), "item_actions": item})
        total_price += Item.query.get(item.item_requested_id).price * item.cart_quantity
    return render_template("shopping-cart.html", cart_items=requested_items, total_price=total_price)


@app.route("/cart-change/<int:cart_item_id>/<qty_change>")
@login_required
def change_qty_cart(cart_item_id, qty_change):
    qty_change = int(qty_change)
    cart_item_to_delete = ItemActions.query.get(cart_item_id)
    if qty_change == 0:
        cart_item_to_delete.cart_quantity = 0
    else:
        cart_item_to_delete.cart_quantity += qty_change
    if cart_item_to_delete.cart_quantity <= 0:
        cart_item_to_delete.cart_quantity = 0
        cart_item_to_delete.in_cart = False
    db.session.commit()
    return redirect(url_for('shopping_cart', item_id=0))


@app.route("/checkout/<int:address_id>", methods=["GET", "POST"])
@login_required
def checkout(address_id):
    cart_items = ItemActions.query.filter_by(creator=current_user, in_cart=True).all()
    total_price = 0
    description = ''
    line_items = []
    for item in cart_items:
        description += f"{Item.query.get(item.item_requested_id).item_name} Qty: {item.cart_quantity}: {Item.query.get(item.item_requested_id).price * item.cart_quantity}\n"
        total_price += Item.query.get(item.item_requested_id).price * item.cart_quantity
        line_items.append({"price": Item.query.get(item.item_requested_id).price_api, "quantity": item.cart_quantity})
    order_codes = [order.order_number for order in OrderHistory.query.all()]
    if not order_codes:
        order_code = 1
    else:
        order_code = int(order_codes[-1]) + 1
    charge = stripe.checkout.Session.create(line_items=line_items,
                                            mode="payment",
                                            success_url=MY_DOMAIN,
                                            cancel_url=MY_DOMAIN,
                                            order_code=order_code) # not the actual attribute
    for item in cart_items:
        item.in_cart = False
        item.cart_quantity = 0
        db.session.commit()
        order = OrderHistory(item_requested_id=item.item_requested_id,
                             order_number=order_code,
                             order_date=date.today().strftime("%d/%m/%Y"),
                             quantity_ordered=item.cart_quantity,
                             creator=current_user,
                             address_id=address_id)
        db.session.add(order)
        db.session.commit()
    return redirect(charge['url'])


@app.route('/stripe_webhooks', methods=['POST'])
def webhook():
    event = None
    endpoint_secret = '' # TODO publish the site to be able to complete the webhook
    payload = request.data
    sig_header = request.headers['STRIPE_SIGNATURE']

    try:
        event = stripe.Webhook.construct_event(
            payload, sig_header, endpoint_secret
        )
    except ValueError as e:
        # Invalid payload
        raise e
    except stripe.error.SignatureVerificationError as e:
        # Invalid signature
        raise e

    # Handle the event
    print('Handled event type {}'.format(event['type']))
    if event == "success":
        cart_items = OrderHistory.query(order_number=event['order_code']).all()
        msg_text = f"Order: {cart_items[0].order_number}\nA new payment was made for the following products:\n"
        for item in cart_items:
            item.paid = True
            db.session.commit()
            msg_text += f"Product: {item.item_requested} Quantity: {item.cart_quantity}"
        address = Address.query(id=cart_items[0].address_id)
        msg_text += f"Send to: {User.query(id=cart_items[0].creator_id)}\n Address: {address.country} {address.region} " \
                    f"{address.city}\n{address.street} {address.street_number}\n{address.address_type}"
        with smtplib.SMTP("smtp.mail.yahoo.com", port=587) as connection:
            connection.starttls()
            connection.login(user=MY_EMAIL, password=PASSWORD)
            connection.sendmail(
                from_addr=MY_EMAIL,
                to_addrs="siskasstavros@gmail.com",
                msg=f"Subject:Order Paid\n\n{msg_text}"
            )
    return jsonify(success=True)  # technically correct but need to send first success response and after the database
# changes and the mail


@app.route("/select-address", methods=["GET", "POST"])
@login_required
def select_address():
    form = AddAddress()
    if request.method == "POST":
        new_address = Address(country=form.country.data,
                              region=form.region.data,
                              city=form.city.data,
                              street=form.street.data,
                              street_number=form.street_number.data,
                              address_type=form.address_type.data,
                              resident=current_user, )
        db.session.add(new_address)
        db.session.commit()
    addresses = Address.query.filter_by(resident=current_user).all()
    print(addresses)
    return render_template("select-address.html", form=form, addresses=addresses)


@app.route("/delete-address/<int:address_id>")
@login_required
def delete_address(address_id):
    address_to_delete = Address.query.get(address_id)
    if OrderHistory.query.get(address_id) is None:
        db.session.delete(address_to_delete)
    else:
        address_to_delete.resident_id = None
    db.session.commit()
    return redirect(url_for("select_address"))


@app.route("/new-post", methods=["GET", "POST"])
@admin_only
def add_new_post():
    form = CreateItem()
    if request.method == "POST":
        image_large, image_icon = resize_image(form.image, form.item_num.data)
        descr = form.description.data
        descr = descr.replace("<p>", "")
        descr = descr.replace("</p>", "")
        new_post = Item(
            item_code=form.item_num.data,
            item_name=form.item_name.data,
            description=descr,
            img_icon=image_icon,
            img_lrg=image_large,
            price=form.price.data,
            category=form.categories.data,
            views=0,
            sold=0
        )
        db.session.add(new_post)
        db.session.commit()
        return redirect(url_for("get_all_posts"))
    return render_template("make-post.html", form=form)


@app.route("/edit-post/<int:item_id>", methods=["GET", "POST"])
@admin_only
def edit_post(item_id):
    item = Item.query.get(item_id)
    edit_form = CreateItem(
        item_num=item.item_code,
        item_name=item.item_name,
        price=item.price,
        description=item.description,
        categories=item.category,
    )
    if request.method == "POST":
        image_icon = None
        image_large = None
        if edit_form.image.data is not None:
            image_large, image_icon = resize_image(edit_form.image, edit_form.item_num.data)
        descr = edit_form.description.data
        descr = descr.replace("<p>", "")
        descr = descr.replace("</p>", "")
        item.item_code = edit_form.item_num.data
        item.item_name = edit_form.item_name.data
        item.description = descr
        if edit_form.image.data is not None:
            item.img_icon = image_icon
            item.img_lrg = image_large
        item.price = edit_form.price.data
        item.category = edit_form.categories.data
        db.session.commit()
        return redirect(url_for("show_item", item_id=item.id))

    return render_template("make-post.html", form=edit_form)


@app.route("/delete/<int:post_id>")
@admin_only
def delete_post(post_id):
    post_to_delete = Item.query.get(post_id)
    db.session.delete(post_to_delete)
    db.session.commit()
    return redirect(url_for('get_all_posts'))


if __name__ == "__main__":
    app.run(debug=True)
