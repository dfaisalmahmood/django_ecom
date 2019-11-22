python manage.py makemigrations
python manage.py migrate
python manage.py create_superuser_with_pass --username root --password 1234 --email blank@email.com --preserve --no-input 
python manage.py collectstatic --no-input
python manage.py runserver