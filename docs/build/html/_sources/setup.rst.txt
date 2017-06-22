.. _setup:

Setup
=====

Dependencies
------------

* Python 3.6
* Pandas
* Heroku (application and command-line tool)
* AWS S3 bucket
* WordPress' TablePress plugin with Table Auto Update extension

Installation
------------

When creating a virtual environment for this project, make sure to use Python 3.4 or later.

.. code-block:: bash

    mkvirtualenv --python=`which python3` oklahoma-watch-salesforce

Install the Python dependencies.

.. code-block:: bash

    pip install -r requirements.txt

Install the Heroku command-line tool. See `this guide <https://devcenter.heroku.com/articles/heroku-command-line>`_ for other operating systems.

.. code-block:: bash

    brew install heroku

Environment variables
---------------------

These environment variables are used through the application. Define them either in ``~/.env``, ``~/.virtualenvs/oklahoma-watch-salesforce/bin/postactivate`` or any other file that is sourced.

.. code-block:: bash

    export HEROKU_APP=oklahoma-watch-salesforce

    export SLACK_THOMASTHOREN_ACCESS_TOKEN=

    export OK_WATCH_SALESFORCE_USERNAME=
    export OK_WATCH_SALESFORCE_PASSWORD=
    export OK_WATCH_SALESFORCE_SECURITY_TOKEN=

    # S3 credentials
    export AWS_ACCESS_KEY_ID=
    export AWS_SECRET_ACCESS_KEY=
    export AWS_DEFAULT_REGION=

Heroku
------

Configure the Heroku application's environment variables by running the ``scripts/config.sh`` script.

Travis CI
---------

Note: Travis CI is only free if your GitHub repo is public.

Make sure the Travis CI gem is installed.

.. code-block:: bash

  gem install travis

Encrypt and add each environment variable by running the ``scripts/config.sh`` script. Note that `Travis CI can't use environment variables containing Bash special characters <https://docs.travis-ci.com/user/encryption-keys#Note-on-escaping-certain-symbols>`_. Make sure all passwords and tokens meet this standard.

AWS S3 bucket
-------------

Create an S3 bucket to store the CSV files for TablePress. This project uses the ``membership.oklahomawatch.org`` bucket.

Tests
-----

Run tests.

.. code-block:: bash

    coverage run --source=scripts -m unittest

Determine the code coverage.

.. code-block:: bash

    coverage report
