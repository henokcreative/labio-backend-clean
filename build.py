#!/usr/bin/env python
import os
import sys
import django
from django.core.management import execute_from_command_line

if __name__ == '__main__':
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'labio.settings')
    django.setup()

    # Run migrations
    execute_from_command_line(['manage.py', 'migrate', '--run-syncdb'])

    # Create superuser if needed (optional)
    # execute_from_command_line(['manage.py', 'createsuperuser', '--noinput'])