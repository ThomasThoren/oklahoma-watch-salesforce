.. _heroku:

Heroku
======

Read the `Getting Started guide <https://devcenter.heroku.com/articles/getting-started-with-python#introduction>`_ if this is your first time working with Heroku.

Create an application to host and run your scripts. This project's slug is ``oklahoma-watch-salesforce``. See the `Heroku applications dashboard <https://dashboard.heroku.com/>`_ for all of your applications.

Make sure to set up an automatic pull from your GitHub repo's master branch. Also install the `Heroku Scheduler <https://scheduler.heroku.com/dashboard>`_ add-on. Configure it to run ``bash scripts/main.sh`` daily.
