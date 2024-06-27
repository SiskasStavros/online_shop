from flask_wtf import FlaskForm
from wtforms import StringField, SubmitField, PasswordField, EmailField, BooleanField, DateField, IntegerField, SelectField, IntegerRangeField
from wtforms.validators import DataRequired, URL, Email, NumberRange, Optional
from flask_wtf.file import FileField, FileRequired, FileAllowed
from flask_ckeditor import CKEditorField


# WTForm
class CreateItem(FlaskForm):
    item_num = StringField("Item Code", validators=[DataRequired()])
    item_name = StringField("Item Name", validators=[DataRequired()])
    image = FileField(validators=[FileAllowed(['jpg', 'png'])])
    price = StringField("Price", validators=[DataRequired()])
    description = CKEditorField("Item Description", validators=[DataRequired()])
    categories = StringField("Categories", validators=[DataRequired()])
    submit = SubmitField("Submit")


class CreateUser(FlaskForm):
    email = EmailField("Email", validators=[DataRequired(), Email(message="Invalid Email")])
    password = PasswordField("Password", validators=[DataRequired()])
    name = StringField("Name", validators=[DataRequired()])
    surname = StringField("Surname", validators=[DataRequired()])
    date_of_birth = DateField('Date of birth', validators=[Optional()])
    submit = SubmitField("Sign Up")


class LogInUser(FlaskForm):
    email = EmailField("Email", validators=[DataRequired(), Email(message="Invalid Email")])
    password = PasswordField("Password", validators=[DataRequired()])
    submit = SubmitField("Log In")


class ReviewForm(FlaskForm):
    review = CKEditorField("Review")
    rating = IntegerRangeField("Rating", validators=[NumberRange(min=1, max=5, message='Range 1 - 5')])
    submit = SubmitField("Submit Review")


class AddAddress(FlaskForm):
    add_types = ["Home", "Work"]
    country = StringField("Country", validators=[DataRequired()])
    region = StringField("Region or State", validators=[DataRequired()])
    city = StringField("City", validators=[DataRequired()])
    street = StringField("Street", validators=[DataRequired()])
    street_number = StringField("Street Number", validators=[DataRequired()])
    address_type = SelectField("Address Type", choices=add_types, validators=[DataRequired()])
    submit = SubmitField("Add Address")
