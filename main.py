from flask import Flask, render_template, request, redirect, url_for, flash
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy import Integer, String, Float, ForeignKey
from flask_wtf import FlaskForm
from wtforms import StringField, SubmitField, FloatField, PasswordField
from wtforms.validators import DataRequired, NumberRange, Email, Length
from flask_bootstrap import Bootstrap4
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from werkzeug.security import generate_password_hash, check_password_hash

'''
Red underlines? Install the required packages first: 
Open the Terminal in PyCharm (bottom left). 

On Windows type:
python -m pip install -r requirements.txt

On MacOS type:
pip3 install -r requirements.txt

This will install the packages from requirements.txt for this project.
'''


# Create Database
class Base(DeclarativeBase):
    pass


app = Flask(__name__)
app.config['SECRET_KEY'] = 'test'
app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///new-books-collection.db"

# Initialize Flask-Bootstrap
Bootstrap4(app)
db = SQLAlchemy(model_class=Base)
db.init_app(app)

# Initialize Flask-Login
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

# Create user table
class User(UserMixin, db.Model):
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    email: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    password: Mapped[str] = mapped_column(String(100), nullable=False)
    name: Mapped[str] = mapped_column(String(100), nullable=False)

@login_manager.user_loader
def load_user(user_id):
    return db.session.execute(db.select(User).where(User.id == user_id)).scalar()


# Create book table
class Book(db.Model):
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    title: Mapped[str] = mapped_column(String(250), nullable=False)
    author: Mapped[str] = mapped_column(String(250), nullable=False)
    rating: Mapped[float] = mapped_column(Float, nullable=False)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey('user.id'), nullable=False)  # Foreign key to link to User table

class LoginForm(FlaskForm):
      email = StringField('Email', validators=[DataRequired(), Email()])
      password = PasswordField('Password', validators=[DataRequired()])
      submit = SubmitField('Login')

class RegisterForm(FlaskForm):
      name = StringField('Name', validators=[DataRequired(), Length(min=2, max=100)])
      email = StringField('Email', validators=[DataRequired(), Email()])
      password = PasswordField('Password', validators=[DataRequired(), Length(min=6)])
      submit = SubmitField('Register')



# Create table schema in the database. Requires application context.
with app.app_context():
    db.create_all()


class BookForm(FlaskForm):
    name = StringField('Book Name', validators=[DataRequired()])
    author = StringField('Book Author', validators=[DataRequired()])
    rating = FloatField('Rating', validators=[DataRequired(), NumberRange(min=0, max=10, message="Rating must be between 0 and 10")])
    submit = SubmitField('Submit')

@app.route("/register", methods=['GET', 'POST'])
def register():
      form = RegisterForm()
      if form.validate_on_submit():
          # Check if user already exists
          existing_user = db.session.execute(db.select(User).where(User.email == form.email.data)).scalar()
          if existing_user:
              flash('Email already registered. Please login.')
              return redirect(url_for('login'))

          # Create new user
          new_user = User(
              email=form.email.data,
              password=generate_password_hash(form.password.data, method='pbkdf2:sha256'),
              name=form.name.data
          )
          db.session.add(new_user)
          db.session.commit()
          login_user(new_user)
          return redirect(url_for('home'))

      return render_template('register.html', form=form)

@app.route("/login", methods=['GET', 'POST'])
def login():
      form = LoginForm()
      if form.validate_on_submit():
          user = db.session.execute(db.select(User).where(User.email == form.email.data)).scalar()
          if user and check_password_hash(user.password, form.password.data):
              login_user(user)
              return redirect(url_for('home'))
          else:
              flash('Invalid email or password')
              return redirect(url_for('login'))

      return render_template('login.html', form=form)

@app.route("/logout")
@login_required
def logout():
      logout_user()
      return redirect(url_for('login'))


@app.route('/')
def home():
    # This is the home page where we display all books
    if current_user.is_authenticated:
        with app.app_context():
            # Query books for the current user only
            all_books = db.session.execute(db.select(Book).where(Book.user_id == current_user.id)).scalars().all()
    else:
        all_books = []

    return render_template('index.html', books=all_books)


@app.route("/add", methods=['GET', 'POST'])
@login_required
def add():
    form = BookForm()

    # Check if the form is submitted
    if form.validate_on_submit():
        # Save to database
        with app.app_context():
            existing_book = db.session.execute(db.select(Book).where(Book.title == form.name.data)).scalar_one_or_none()
            if existing_book is None:
                new_book = Book(title=form.name.data, author=form.author.data, rating=form.rating.data, user_id=current_user.id )
                db.session.add(new_book)
                db.session.commit()
        return redirect(url_for('home'))

    return render_template('add.html', form=form)


@app.route("/edit/<book_id>", methods=['GET', 'POST'])
@login_required
def edit(book_id):
        # Get new rating from the form
        # Update the book's rating in the database
        with app.app_context():
            book_to_update = db.session.execute(db.select(Book).where(Book.id == book_id, Book.user_id == current_user.id)).scalar()
            
            if not book_to_update:
                flash('Book not found or access denied')
                return redirect(url_for('home'))

            if request.method == "POST":
                try:
                    new_rating = float(request.form.get('rating'))
                    if 0 <= new_rating <= 10:
                        book_to_update.rating = new_rating
                        db.session.commit()
                        return redirect(url_for('home'))
                except (ValueError, TypeError):
                    pass
        return render_template('edit.html', book=book_to_update)

@app.route("/delete/<book_id>", methods=['POST'])
@login_required
def delete(book_id):
    with app.app_context():
        book_to_delete = db.session.execute(db.select(Book).where(Book.id == book_id, Book.user_id == current_user.id)).scalar()
        
        if not book_to_delete:
            flash('Book not found or access denied')
            return redirect(url_for('home'))
            
        db.session.delete(book_to_delete)
        db.session.commit()
        return redirect(url_for('home'))


if __name__ == "__main__":
    app.run(debug=True)
